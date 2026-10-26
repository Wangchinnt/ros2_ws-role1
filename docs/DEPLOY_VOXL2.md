# Deploying uav_nav to the VOXL 2 (handoff to Role 4)

This is the hand-off from Role 1 (flight control & navigation) to Role 4 (integration & safety).
It lists what has been verified, what must be checked on the drone, and the exact commands.

**Status legend**: ✅ verified (with log), ⚠️ verified in simulation only, ❓ TO CONFIRM on the drone.

## 1. What uav_nav does

`gps_goto` flies PX4 through a list of GPS waypoints in **Offboard** mode over **MAVROS**:
wait for GPS → stream setpoints → OFFBOARD + arm → take off → for each waypoint: fly, accept
within a radius, hold → land. Full description: [README](../README.md#gps_goto-node).

```
 gps_goto ──ROS 2──► MAVROS (mavros_node) ──MAVLink/UDP──► voxl-mavlink-server ──► PX4 (on VOXL 2)
```

## 2. What has been verified

| Item | Status | Evidence |
|---|---|---|
| Fly to GPS waypoints, error after hold 0.1–0.4 m | ⚠️ | `results/report1_2026-09-28/mavlink/`, `results/report2_2026-10-26/foxy/` |
| ROS 2 **Foxy** + MAVROS **2.4.0** (same versions as VOXL 2) | ⚠️ Docker on x86 | [FOXY_DOCKER.md](FOXY_DOCKER.md) |
| Failsafe: node killed, pilot takeover, GPS loss → lands | ⚠️ | `results/report1_2026-09-28/failsafe/`, `results/report2_2026-10-26/foxy/…_gps_loss` |
| Through a MAVLink router (stand-in for `voxl-mavlink-server`) | ⚠️ `mavlink-router` | `results/report1_2026-09-28/mavlink/…_router` |
| NTUT East Dorm field mission + 3 m/s wind | ⚠️ | `results/report2_2026-10-26/ntut/` |
| Runs on the VOXL 2 itself (arm64) | ❓ | |
| MAVROS ↔ `voxl-mavlink-server` connection | ❓ | |
| Real GPS (uBlox M10) accuracy vs `max_eph` / `acceptance_radius` | ❓ | |

Two Foxy-only bugs were found and fixed on 2026-10-26 (details in [FOXY_DOCKER.md §5](FOXY_DOCKER.md#5-foxy-problems-found-and-fixed)):
the MAVROS 2.4.0 launch files are ROS 1 format, and its `gp_origin` is in ECEF.
**Do not deploy a version older than these fixes.**

## 3. Questions for Role 4 (answers needed before the first flight)

1. ❓ Is ROS 2 Foxy + `ros-foxy-mavros` installed on the VOXL 2, or should uav_nav run in a Docker
   container there (the same `docker/foxy/Dockerfile` should build on arm64: `ros:foxy-ros-base`
   is multi-arch, not tried)?
2. ❓ Which UDP port does `voxl-mavlink-server` expose for an onboard MAVROS? ModalAI's docs
   mention enabling `en_localhost_mavlink_udp` in `voxl-vision-hub` for local MAVROS/MAVSDK
   (<https://docs.modalai.com/voxl-mavlink-server/>). The `fcu_url` below depends on this.
3. ❓ PX4 version on the drone (SITL tests used v1.14.0).
4. ❓ Current values of `COM_OF_LOSS_T`, `COM_OBL_RC_ACT`, `COM_RC_LOSS_T`, `NAV_RCL_ACT`, geofence `GF_*`.
5. ❓ Who holds the RC, and which switch takes manual control (Position mode)?

## 4. Install

### Option A: native ROS 2 Foxy on the VOXL 2

```bash
# on the VOXL 2 (adb shell or ssh)
mkdir -p ~/ros2_ws/src && cd ~/ros2_ws/src
git clone https://github.com/Wangchinnt/ros2_ws-role1.git role1
ln -s role1/src/uav_nav uav_nav          # only uav_nav is needed on the drone
cd ~/ros2_ws
source /opt/ros/foxy/setup.bash
rosdep install --from-paths src/uav_nav --ignore-src -y    # mavros, mavros_msgs, geographic_msgs, ...
sudo /opt/ros/foxy/lib/mavros/install_geographiclib_datasets.sh   # once, MAVROS needs it
colcon build --packages-select uav_nav
source install/setup.bash
```

### Option B: Docker on the VOXL 2

```bash
docker build -t uav_nav_foxy role1/docker/foxy/
docker run --rm -it --net=host -v $PWD/role1/src/uav_nav:/ws/src/uav_nav:ro uav_nav_foxy bash
# then inside the container: the same colcon build / ros2 launch as in FOXY_DOCKER.md §3
```

## 5. Bench test (props OFF)

Do this on the bench before any flight. It checks the MAVLink connection and the GPS, without flying.

```bash
# 1. MAVROS alone, check the connection
ros2 run mavros mavros_node --ros-args -p fcu_url:=<FCU_URL from question 2>
ros2 topic echo --once /mavros/state                  # connected: true
ros2 topic echo --once /mavros/gpsstatus/gps1/raw     # fix_type >= 3 outdoors, h_acc in mm
ros2 topic echo --once /mavros/global_position/global
```

```bash
# 2. Check the EKF origin conversion (the Foxy ECEF bug). PROPS OFF: the node will arm.
ros2 launch uav_nav gps_goto.launch.py fcu_url:=<FCU_URL> config:=gps_goto_ntut.yaml
#    Expect:  Projection origin: gp_origin (25.04..., 121.53...) converted from ECEF (...)
#    and every "WPn ... distance" below ~100 m (on the NTUT field).
#    Millions of metres = a version without the fix: STOP and update the code.
#    Then press Ctrl+C: the node stops streaming setpoints and PX4 handles it (COM_OBL_RC_ACT).
```

## 6. Launch on the drone

```bash
ros2 launch uav_nav gps_goto.launch.py fcu_url:=<FCU_URL> config:=gps_goto_ntut.yaml
ros2 launch uav_nav gps_goto.launch.py fcu_url:=<FCU_URL> waypoints:="[25.042224, 121.537790, 8.0]"
ros2 launch uav_nav gps_goto.launch.py fcu_url:=<FCU_URL> waypoint_frame:=offset waypoints:="[10, 0, 5]"
```

| Argument | Use on the drone |
|---|---|
| `fcu_url` | **required**: the `voxl-mavlink-server` endpoint (question 2). The default `udp://:14540@127.0.0.1:14557` is the SITL one |
| `config` | waypoint file in `config/`; edit a copy for each test site |
| `waypoints` | `"[a, b, alt, ...]"` overrides the file's waypoints from the terminal |
| `waypoint_frame` | `gps` (`[lat, lon, alt_rel]`) or `offset` (`[north_m, east_m, alt_rel]` from takeoff) |
| `start_mavros:=false` | if MAVROS is already running on the drone (then `fcu_url` is not used) |
| `router` | leave `false`: `voxl-mavlink-server` is the router |

When `gps_goto` exits (mission done or aborted) the launch also stops MAVROS.

### Parameters to review for the real drone

| Parameter | SITL value | Suggestion for first flights |
|---|---|---|
| `takeoff_alt` | 5.0 m | 3–5 m |
| `acceptance_radius` | 1.0 m | **~2 m** (uBlox M10 noise is larger than SITL's) ❓ |
| `max_eph` | 3.0 m | keep 3.0; check typical `h_acc` on the field first |
| `max_drift` | 3.0 m | keep; lands if the drone drifts during takeoff |
| `wp_timeout` | 90 s | keep |
| `hold_time` | 3–5 s | keep |
| `max_wp_distance` | 500 m | ~100 m on the NTUT field (the farthest waypoint is 39 m away) |
| `max_alt` | 50 m | ~20 m for first flights |

## 7. Safety behaviour (what the node does / does not do)

- If the mode is no longer OFFBOARD while flying (pilot switched, or PX4 failsafe), the node
  **aborts and stops sending commands**. It never fights the pilot for control.
- Before arming, every waypoint is checked against `max_wp_distance` and `max_alt`; a wrong
  coordinate stops the node on the ground (tested: `results/report2_2026-10-26/ntut/…_wrong_waypoint_abort`).
- If GPS degrades (`fix_type < 3` or `h_acc > max_eph`) or the drone drifts during takeoff, it commands LAND.
- If the node or the computer dies, PX4 loses setpoints and after `COM_OF_LOSS_T` (default 1 s)
  executes `COM_OBL_RC_ACT`. In SITL (no RC) this ended with a landing at 27.9 s.
- The node has **no obstacle avoidance** (that is Role 3) and **no geofence**: rely on PX4's geofence.

## 8. Field test

See [FIELD_TEST_PLAN.md](FIELD_TEST_PLAN.md).
