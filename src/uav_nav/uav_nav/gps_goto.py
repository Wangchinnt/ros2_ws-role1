"""
gps_goto: fly PX4 to one or more GPS coordinates in Offboard mode, over MAVLink (MAVROS).

Flow: read GPS/position from MAVROS -> convert target lat/lon to local (geo.py)
-> stream position setpoints continuously (20 Hz, which is also the MAVLink Offboard "heartbeat")
-> switch to Offboard + arm (MAVROS services) -> take off -> fly through each waypoint
(accepted once inside acceptance_radius) -> hold position -> land (AUTO.LAND).

Link: node <-> MAVROS <-> MAVLink (UDP 14540 on SITL; on VOXL 2 routed by
voxl-mavlink-server) <-> PX4.

Frame note: PX4 uses NED, MAVROS converts to ENU (x=East, y=North, z=Up)
for every ROS topic. This node works entirely in MAVROS ENU.

State: WAIT_READY -> PRE_STREAM -> ENGAGE -> TAKEOFF -> GOTO -> HOLD -> (GOTO ...)
       -> LANDING -> DONE (or FINAL_HOLD if land_at_end=false); error -> ABORT.
       ENGAGE timed out while armed -> DISARM (disarm on the ground) -> ABORT.
"""
import math

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from geographic_msgs.msg import GeoPointStamped
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import GPSRAW, State
from mavros_msgs.srv import CommandBool, CommandLong, SetMode
from sensor_msgs.msg import NavSatFix

from uav_nav.geo import haversine, MapProjection

RATE_HZ = 20.0
PRE_STREAM_SEC = 1.0      # PX4 only enters Offboard once setpoints are streaming
ORIGIN_WAIT_SEC = 5.0     # max wait for gp_origin, then use the current position as origin
ENGAGE_TIMEOUT_SEC = 10.0  # max time to request OFFBOARD + arm
DISARM_TIMEOUT_SEC = 5.0   # max time to request disarm before giving up
MAV_CMD_REQUEST_MESSAGE = 512
MAVLINK_MSG_ID_GPS_GLOBAL_ORIGIN = 49


class GpsGoto(Node):

    def __init__(self):
        super().__init__('gps_goto')

        # Every parameter has a default (works on both Foxy and Humble).
        # waypoints: flat list [lat, lon, alt_rel, lat, lon, alt_rel, ...],
        # alt_rel = altitude (m) relative to the takeoff point.
        self.declare_parameter('waypoints', [47.398200, 8.546200, 10.0])
        self.declare_parameter('takeoff_alt', 5.0)
        self.declare_parameter('acceptance_radius', 1.0)   # m, horizontal
        self.declare_parameter('acceptance_alt', 1.0)      # m, vertical
        self.declare_parameter('hold_time', 5.0)           # s to hold position at each waypoint
        self.declare_parameter('wp_timeout', 90.0)         # s max per leg
        self.declare_parameter('max_eph', 3.0)             # m, do not fly with worse GPS
        self.declare_parameter('max_drift', 3.0)           # m, takeoff horizontal drift -> LAND
        self.declare_parameter('land_at_end', True)

        flat = list(self.get_parameter('waypoints').value)
        if len(flat) == 0 or len(flat) % 3 != 0:
            raise ValueError('waypoints must be a multiple of 3: [lat, lon, alt_rel, ...]')
        self.waypoints = [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]
        self.takeoff_alt = self.get_parameter('takeoff_alt').value
        self.acc_radius = self.get_parameter('acceptance_radius').value
        self.acc_alt = self.get_parameter('acceptance_alt').value
        self.hold_time = self.get_parameter('hold_time').value
        self.wp_timeout = self.get_parameter('wp_timeout').value
        self.max_eph = self.get_parameter('max_eph').value
        self.max_drift = self.get_parameter('max_drift').value
        self.land_at_end = self.get_parameter('land_at_end').value

        # Best-effort subscribers: compatible with any publisher (reliable or best-effort).
        qos = qos_profile_sensor_data
        self.create_subscription(State, '/mavros/state', self.on_state, qos)
        self.create_subscription(PoseStamped, '/mavros/local_position/pose', self.on_pose, qos)
        self.create_subscription(NavSatFix, '/mavros/global_position/global',
                                 self.on_global, qos)
        self.create_subscription(GPSRAW, '/mavros/gpsstatus/gps1/raw', self.on_gps, qos)
        self.create_subscription(GeoPointStamped, '/mavros/global_position/gp_origin',
                                 self.on_origin, qos)

        self.pub_sp = self.create_publisher(PoseStamped, '/mavros/setpoint_position/local', 10)
        self.cli_mode = self.create_client(SetMode, '/mavros/set_mode')
        self.cli_arm = self.create_client(CommandBool, '/mavros/cmd/arming')
        self.cli_cmd = self.create_client(CommandLong, '/mavros/cmd/command')

        self.state_msg = None
        self.pose = None
        self.glob = None
        self.gps = None
        self.origin = None

        self.finished = False     # True on DONE/ABORT -> main() exits
        self.state = 'WAIT_READY'
        self.state_since = self.now_s()
        self.tick = 0
        self.home = None          # PoseStamped at start
        self.targets = []         # [(x_east, y_north, z_up)] in MAVROS ENU
        self.wp_idx = 0
        self.setpoint = None      # (x, y, z) ENU

        self.create_timer(1.0 / RATE_HZ, self.loop)
        self.get_logger().info('gps_goto (MAVLink/MAVROS): %d waypoint, takeoff %.1f m, '
                               'radius %.1f m'
                               % (len(self.waypoints), self.takeoff_alt, self.acc_radius))

    # ---------- callbacks ----------
    def on_state(self, msg):
        self.state_msg = msg

    def on_pose(self, msg):
        self.pose = msg

    def on_global(self, msg):
        self.glob = msg

    def on_gps(self, msg):
        self.gps = msg

    def on_origin(self, msg):
        self.origin = msg

    # ---------- helpers ----------
    def now_s(self):
        return self.get_clock().now().nanoseconds / 1e9

    def set_state(self, state):
        self.get_logger().info('[%s] -> [%s]' % (self.state, state))
        self.state = state
        self.state_since = self.now_s()
        if state in ('DONE', 'ABORT'):
            self.finished = True

    def elapsed(self):
        return self.now_s() - self.state_since

    def every(self, sec):
        return self.tick % max(1, int(RATE_HZ * sec)) == 0

    def gps_eph(self):
        """
        GPS horizontal accuracy (m), taken from GPSRAW.h_acc (mm).

        Note: GPSRAW.eph is HDOP x 100 (unitless), NOT meters
        (PX4 GPS_RAW_INT.hpp: eph = hdop * 100, h_acc = eph[m] * 1000).
        h_acc = 0 means unknown -> treat GPS as not good enough.
        """
        if self.gps is None or self.gps.h_acc == 0:
            return None
        return self.gps.h_acc / 1000.0

    def gps_ok(self):
        """GPS good enough to fly: 3D fix or better and horizontal accuracy <= max_eph."""
        eph = self.gps_eph()
        return (self.gps is not None and self.gps.fix_type >= 3
                and eph is not None and eph <= self.max_eph)

    def connected(self):
        return self.state_msg is not None and self.state_msg.connected

    def is_armed(self):
        return self.state_msg is not None and self.state_msg.armed

    def is_offboard(self):
        return self.state_msg is not None and self.state_msg.mode == 'OFFBOARD'

    def pos(self):
        p = self.pose.pose.position
        return p.x, p.y, p.z

    def request_mode(self, mode):
        if self.cli_mode.service_is_ready():
            req = SetMode.Request()
            req.custom_mode = mode
            self.cli_mode.call_async(req)

    def request_origin(self):
        """Ask PX4 for GPS_GLOBAL_ORIGIN -> MAVROS publishes /mavros/global_position/gp_origin."""
        if self.cli_cmd.service_is_ready():
            req = CommandLong.Request()
            req.command = MAV_CMD_REQUEST_MESSAGE
            req.param1 = float(MAVLINK_MSG_ID_GPS_GLOBAL_ORIGIN)
            self.cli_cmd.call_async(req)

    def request_arm(self, value=True):
        """value=True: arm, value=False: disarm."""
        if self.cli_arm.service_is_ready():
            req = CommandBool.Request()
            req.value = value
            self.cli_arm.call_async(req)

    def publish_setpoint(self):
        x, y, z = self.setpoint
        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.pose.position.x = float(x)
        msg.pose.position.y = float(y)
        msg.pose.position.z = float(z)
        msg.pose.orientation = self.home.pose.orientation  # keep the heading from takeoff
        self.pub_sp.publish(msg)

    def dist_to_setpoint(self):
        x, y, z = self.pos()
        sx, sy, sz = self.setpoint
        return math.hypot(x - sx, y - sy), abs(z - sz)

    # ---------- state machine, 20 Hz ----------
    def loop(self):
        self.tick += 1
        if self.state in ('DONE', 'ABORT'):
            return

        if self.state == 'WAIT_READY':
            ready = (self.connected() and self.pose is not None and self.glob is not None
                     and self.gps_ok()
                     and self.cli_mode.service_is_ready() and self.cli_arm.service_is_ready())
            # Prefer the PX4 EKF origin (gp_origin). PX4 does not send it on its own -> request
            # every 1 s, wait up to ORIGIN_WAIT_SEC before using the fallback origin.
            if self.origin is None and self.connected() and self.every(1.0):
                self.request_origin()
            if ready and self.origin is None and self.elapsed() < ORIGIN_WAIT_SEC:
                ready = False
            if not ready:
                if self.every(2.0):
                    self.get_logger().info(
                        'Waiting for ready: connected=%s pose=%s global=%s gps_fix=%s eph=%s '
                        'origin=%s'
                        % (self.connected(), self.pose is not None, self.glob is not None,
                           None if self.gps is None else self.gps.fix_type,
                           None if self.gps_eph() is None else round(self.gps_eph(), 2),
                           self.origin is not None))
                return
            self.plan()
            self.set_state('PRE_STREAM')

        # From here on: stream a setpoint every cycle (PX4 needs >= 2 Hz, otherwise failsafe).
        if self.state not in ('LANDING',):
            self.publish_setpoint()

        flying = self.state in ('TAKEOFF', 'GOTO', 'HOLD', 'FINAL_HOLD')
        # Safety: lost Offboard in flight (pilot took over / failsafe) -> stop intervening.
        if flying and not self.is_offboard():
            self.get_logger().error('Lost Offboard (mode=%s) -> ABORT, PX4 handles failsafe'
                                    % self.state_msg.mode)
            self.set_state('ABORT')
            return
        # Safety: GPS degraded mid-flight -> land.
        if flying and not self.gps_ok():
            self.get_logger().error('GPS degraded (fix_type=%d, h_acc=%s m) -> LAND'
                                    % (self.gps.fix_type, self.gps_eph()))
            self.land()
            return

        if self.state == 'PRE_STREAM':
            if self.elapsed() >= PRE_STREAM_SEC:
                self.set_state('ENGAGE')

        elif self.state == 'ENGAGE':
            if self.is_offboard() and self.is_armed():
                x, y, z = self.pos()
                self.setpoint = (x, y, z + self.takeoff_alt)
                self.set_state('TAKEOFF')
            elif self.elapsed() > ENGAGE_TIMEOUT_SEC:
                if self.is_armed():
                    # Armed but not in OFFBOARD: never leave the drone armed on the ground.
                    self.get_logger().error(
                        'Could not enter Offboard after %.0f s (armed) -> DISARM'
                        % ENGAGE_TIMEOUT_SEC)
                    self.set_state('DISARM')
                else:
                    self.get_logger().error('Could not enter Offboard/arm after %.0f s -> ABORT'
                                            % ENGAGE_TIMEOUT_SEC)
                    self.set_state('ABORT')
            elif self.every(1.0):  # resend every 1 s
                if not self.is_offboard():
                    self.request_mode('OFFBOARD')
                elif not self.is_armed():
                    self.request_arm()

        elif self.state == 'TAKEOFF':
            dxy, dz = self.dist_to_setpoint()
            if dxy > self.max_drift:
                # The takeoff setpoint keeps x, y fixed: large horizontal drift means something is
                # wrong (strong wind, pushed along the ground, bad position estimate) -> land now.
                self.get_logger().error(
                    'Horizontal drift %.1f m during takeoff (> max_drift %.1f m) -> LAND'
                    % (dxy, self.max_drift))
                self.land()
            elif dz < self.acc_alt:
                self.start_waypoint(0)
            elif self.elapsed() > self.wp_timeout:
                self.get_logger().error('Takeoff timeout -> LAND')
                self.land()

        elif self.state == 'GOTO':
            dxy, dz = self.dist_to_setpoint()
            if self.every(1.0):
                self.get_logger().info('WP%d: %.1f m horizontal, %.1f m vertical to go'
                                       % (self.wp_idx + 1, dxy, dz))
            if dxy < self.acc_radius and dz < self.acc_alt:
                lat, lon, _ = self.waypoints[self.wp_idx]
                err = haversine(lat, lon, self.glob.latitude, self.glob.longitude)
                self.get_logger().info(
                    'REACHED WP%d: current GPS (%.7f, %.7f), error %.2f m from target'
                    % (self.wp_idx + 1, self.glob.latitude, self.glob.longitude, err))
                self.set_state('HOLD')
            elif self.elapsed() > self.wp_timeout:
                self.get_logger().error('Timeout WP%d -> LAND' % (self.wp_idx + 1))
                self.land()

        elif self.state == 'HOLD':
            if self.elapsed() >= self.hold_time:
                lat, lon, _ = self.waypoints[self.wp_idx]
                self.get_logger().info(
                    'After holding %.0f s at WP%d: error %.2f m from target'
                    % (self.hold_time, self.wp_idx + 1,
                       haversine(lat, lon, self.glob.latitude, self.glob.longitude)))
                if self.wp_idx + 1 < len(self.targets):
                    self.start_waypoint(self.wp_idx + 1)
                elif self.land_at_end:
                    self.land()
                else:
                    self.get_logger().info('No more waypoints, holding position (Offboard)')
                    self.set_state('FINAL_HOLD')

        elif self.state == 'DISARM':
            if not self.is_armed():
                self.get_logger().info('Disarmed on the ground.')
                self.set_state('ABORT')
            elif self.elapsed() > DISARM_TIMEOUT_SEC:
                self.get_logger().error(
                    'Could not disarm after %.0f s -> ABORT, manual action required'
                    % DISARM_TIMEOUT_SEC)
                self.set_state('ABORT')
            elif self.every(1.0):
                self.request_arm(False)

        elif self.state == 'LANDING':
            if self.every(1.0) and self.state_msg.mode != 'AUTO.LAND' and self.is_armed():
                self.request_mode('AUTO.LAND')  # resend if the previous request did not take
            if not self.is_armed():
                self.get_logger().info('Landed and disarmed. Done.')
                self.set_state('DONE')

    def plan(self):
        """Fix the projection origin and convert every GPS waypoint to MAVROS ENU."""
        self.home = self.pose
        x0, y0, z0 = self.pos()
        self.setpoint = (x0, y0, z0)
        if self.origin is not None:
            # PX4 local origin (EKF origin) -> matches exactly how PX4 converts GPS to local.
            g = self.origin.position
            proj = MapProjection(g.latitude, g.longitude)
            off_n, off_e = 0.0, 0.0
            src = 'gp_origin (%.7f, %.7f)' % (g.latitude, g.longitude)
        else:
            # Fallback: current position as origin plus offset (mm-level difference at ~100 m).
            proj = MapProjection(self.glob.latitude, self.glob.longitude)
            off_n, off_e = y0, x0
            src = 'current position (no gp_origin received)'
        self.get_logger().info('Projection origin: %s' % src)

        self.targets = []
        for i, (lat, lon, alt_rel) in enumerate(self.waypoints):
            n, e = proj.project(lat, lon)
            x, y, z = off_e + e, off_n + n, z0 + alt_rel   # NED -> ENU: x=East, y=North, z=Up
            self.targets.append((x, y, z))
            self.get_logger().info(
                'WP%d GPS (%.7f, %.7f, +%.1f m) -> ENU (E %.2f, N %.2f, U %.2f), distance %.1f m'
                % (i + 1, lat, lon, alt_rel, x, y, z, math.hypot(x - x0, y - y0)))

    def start_waypoint(self, idx):
        self.wp_idx = idx
        self.setpoint = self.targets[idx]
        self.set_state('GOTO')

    def land(self):
        self.request_mode('AUTO.LAND')
        self.set_state('LANDING')


def main(args=None):
    rclpy.init(args=args)
    node = GpsGoto()
    try:
        while rclpy.ok() and not node.finished:
            rclpy.spin_once(node, timeout_sec=0.05)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
