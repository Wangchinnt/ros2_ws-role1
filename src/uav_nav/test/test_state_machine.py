"""
Unit tests for the gps_goto state machine, no SITL needed.

Fakes: MAVROS messages (State, PoseStamped, GPSRAW, NavSatFix) are assigned directly to the node,
service clients and the publisher are replaced by fakes that record calls.
Time: shift state_since back to simulate how long we have been in a state;
set tick = 19 so every(1.0) is true on the next loop() (20 Hz).
"""
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import GPSRAW, State
import pytest
import rclpy
from sensor_msgs.msg import NavSatFix

from uav_nav.gps_goto import DISARM_TIMEOUT_SEC, ENGAGE_TIMEOUT_SEC, GpsGoto


class FakeClient(object):

    def __init__(self):
        self.calls = []

    def service_is_ready(self):
        return True

    def call_async(self, req):
        self.calls.append(req)


class FakePub(object):

    def __init__(self):
        self.msgs = []

    def publish(self, msg):
        self.msgs.append(msg)


@pytest.fixture
def node():
    rclpy.init()
    n = GpsGoto()
    n.cli_mode, n.cli_arm, n.cli_cmd = FakeClient(), FakeClient(), FakeClient()
    n.pub_sp = FakePub()
    n.state_msg = State(connected=True, armed=False, mode='AUTO.LOITER')
    n.pose = pose(0.0, 0.0, 0.0)
    n.home = n.pose
    n.gps = GPSRAW(fix_type=3, h_acc=900)       # 0.9 m, like SITL
    n.glob = NavSatFix(latitude=47.397742, longitude=8.545594)
    n.setpoint = (0.0, 0.0, 0.0)
    yield n
    n.destroy_node()
    rclpy.shutdown()


def pose(x, y, z):
    p = PoseStamped()
    p.pose.position.x, p.pose.position.y, p.pose.position.z = x, y, z
    p.pose.orientation.w = 1.0
    return p


def enter(n, state, seconds_ago=0.0):
    n.state = state
    n.state_since = n.now_s() - seconds_ago
    n.tick = 19


def test_engage_timeout_not_armed_aborts(node):
    enter(node, 'ENGAGE', ENGAGE_TIMEOUT_SEC + 1)
    node.loop()
    assert node.state == 'ABORT' and node.finished


def test_engage_timeout_armed_disarms_then_aborts(node):
    node.state_msg.armed = True                   # armed but mode is not OFFBOARD
    enter(node, 'ENGAGE', ENGAGE_TIMEOUT_SEC + 1)
    node.loop()
    assert node.state == 'DISARM' and not node.finished

    node.tick = 19
    node.loop()                                   # every(1 s) -> send disarm
    assert node.cli_arm.calls and node.cli_arm.calls[-1].value is False

    node.state_msg.armed = False                  # PX4 confirms disarmed
    node.loop()
    assert node.state == 'ABORT' and node.finished


def test_disarm_gives_up_after_timeout(node):
    node.state_msg.armed = True
    enter(node, 'DISARM', DISARM_TIMEOUT_SEC + 1)
    node.loop()
    assert node.state == 'ABORT'


def test_takeoff_drift_lands(node):
    node.state_msg = State(connected=True, armed=True, mode='OFFBOARD')
    node.setpoint = (0.0, 0.0, 5.0)
    node.pose = pose(4.0, 0.0, 1.0)               # 4 m horizontal drift > max_drift 3 m
    enter(node, 'TAKEOFF')
    node.loop()
    assert node.state == 'LANDING'
    assert node.cli_mode.calls[-1].custom_mode == 'AUTO.LAND'


def test_takeoff_normal_goes_to_first_waypoint(node):
    node.state_msg = State(connected=True, armed=True, mode='OFFBOARD')
    node.targets = [(45.0, 50.0, 10.0)]
    node.setpoint = (0.0, 0.0, 5.0)
    node.pose = pose(0.3, -0.2, 4.6)              # 0.36 m horizontal, 0.4 m vertical off
    enter(node, 'TAKEOFF')
    node.loop()
    assert node.state == 'GOTO' and node.setpoint == (45.0, 50.0, 10.0)


def test_mode_change_in_flight_aborts(node):
    node.state_msg = State(connected=True, armed=True, mode='AUTO.LOITER')  # pilot takes over
    node.setpoint = (45.0, 50.0, 10.0)
    enter(node, 'GOTO')
    node.loop()
    assert node.state == 'ABORT'


def test_gps_lost_in_flight_lands(node):
    node.state_msg = State(connected=True, armed=True, mode='OFFBOARD')
    node.gps = GPSRAW(fix_type=0, h_acc=100000)   # like SIM_GPS_USED=0: no fix, 100 m
    node.setpoint = (45.0, 50.0, 10.0)
    enter(node, 'GOTO')
    node.loop()
    assert node.state == 'LANDING'


def test_gps_h_acc_not_eph(node):
    # eph is HDOP*100: 70 (HDOP 0.7) is not 0.7 m; h_acc 5000 mm = 5 m > max_eph 3 m
    node.gps = GPSRAW(fix_type=3, eph=70, h_acc=5000)
    assert node.gps_eph() == 5.0 and not node.gps_ok()
