# Running uav_nav on ROS 2 Foxy (Docker)

The drone's VOXL 2 runs **ROS 2 Foxy** (Ubuntu 20.04, Python 3.8, MAVROS 2.4.0 from apt).
The dev laptop runs **Humble** (Ubuntu 22.04, Python 3.10, MAVROS 2.15.1 built from source).
This guide runs the exact Foxy software stack in a Docker container on the laptop, so
Foxy-only problems show up here and not on the drone.

Everything below was run on 2026-10-26; the outputs shown are copied from those runs.

```
 Host (Ubuntu 22.04)                          Docker container "uav_nav_foxy" (ros:foxy-ros-base)
 ┌───────────────────────────────┐            ┌──────────────────────────────────────────────┐
 │ PX4 SITL v1.14 + Gazebo       │  UDP 14540 │ MAVROS 2.4.0 (apt)  ◄──►  gps_goto (uav_nav) │
 │ (make px4_sitl gz_x500)       │ ◄────────► │ Python 3.8, built with colcon at start-up    │
 └───────────────────────────────┘ --net=host └──────────────────────────────────────────────┘
```

The source code is **mounted read-only** into the container (`-v src/uav_nav:/ws/src/uav_nav:ro`),
so the image never needs rebuilding after a code change.

## 1. Install Docker (once)

```bash
sudo apt update && sudo apt install -y docker.io
sudo usermod -aG docker $USER      # run docker without sudo
```

Log out and log in again for the group change to apply. Until then, prefix commands with
`sg docker -c "..."`, for example `sg docker -c "bash docker/foxy/foxy_test.sh"`.

Check:

```bash
docker --version                   # Docker version 29.1.3, build 29.1.3-0ubuntu3~22.04.2
systemctl is-active docker         # active
```

> `sudo` cannot read a password inside Claude Code's `!` prompt
> (`sudo: a terminal is required to read the password`); run the install in a normal terminal.

## 2. Build the image and run the unit tests

```bash
cd ~/coding/ros2_ws
bash docker/foxy/foxy_test.sh
```

What it does (`docker/foxy/foxy_test.sh`):

1. `docker build -t uav_nav_foxy docker/foxy/`: `ros:foxy-ros-base` + `ros-foxy-mavros`,
   `ros-foxy-mavros-extras`, `ros-foxy-geographic-msgs`, pytest, colcon, GeographicLib datasets.
   The first build downloads ~1 GB and takes a few minutes; later runs use the cache.
2. Starts a container, runs `colcon build --packages-select uav_nav` (into `/tmp`, because `src` is read-only).
3. Prints Python and MAVROS versions, runs `test_geo.py` + `test_state_machine.py`, imports the node.

Expected end of output (from `results/foxy/unit_20261026_192130/foxy_test.log`):

```
Successfully tagged uav_nav_foxy:latest
Python 3.8.10
mavros 2.4.0-1focal.20230606.041241
...................                                                      [100%]
19 passed in 0.68 seconds
import gps_goto OK on Foxy
```

## 3. Fly in SITL with the Foxy container

`sitl_test.sh` starts PX4 SITL on the host; with `FOXY=1` it runs MAVROS + `gps_goto`
inside the container instead of on the host. Requires the image from step 2.

```bash
cd ~/coding/ros2_ws
FOXY=1 bash src/uav_nav/scripts/sitl_test.sh                              # 1 waypoint, NTUT field
FOXY=1 bash src/uav_nav/scripts/sitl_test.sh config:=gps_goto_ntut.yaml   # 3 waypoints, NTUT field
SCENARIO=gps_loss FOXY=1 bash src/uav_nav/scripts/sitl_test.sh            # GPS lost mid-flight
FOXY=1 bash src/uav_nav/scripts/demo_up.sh                                # GUI demo with the Foxy node

# The first Foxy runs (table in section 4) were at PX4's default location, Zurich:
SIM_HOME="47.397742 8.545594 488.0" FOXY=1 bash src/uav_nav/scripts/sitl_test.sh config:=gps_goto_abc.yaml
```

Each run writes `results/sitl_test_<time>_foxy/` (`gps_goto.log`, `px4.log`, `flight.ulg`, `summary.txt`)
and prints the summary. A good run ends with (this one at Zurich, the default before 2026-10-26):

```
Projection origin: gp_origin (47.3977472, 8.5455928) converted from ECEF (4277582.5, 642769.3, 4672204.0)
REACHED WP1: current GPS (47.3981957, 8.5461927), error 0.73 m from target
After holding 5 s at WP1: error 0.22 m from target
Landed and disarmed. Done.
--- conclusion: drone landed and disarmed
```

Only `SCENARIO=none|gps_loss` are supported with `FOXY=1` (`kill_node` and `mode_switch` act on
host processes / the host ROS graph). The container uses `ROS_DOMAIN_ID=42` so it never mixes with
Humble nodes on the host.

### Manual run (without sitl_test.sh)

```bash
# Terminal 1: PX4 SITL on the host (set_sim_home.sh once: PX4 saves the home to disk)
bash ~/coding/ros2_ws/src/uav_nav/scripts/set_sim_home.sh
cd ~/coding/tools/PX4-Autopilot && make px4_sitl gz_x500

# Terminal 2: MAVROS + gps_goto on Foxy
cd ~/coding/ros2_ws
bash docker/foxy/foxy_test.sh fly
```

`foxy_test.sh fly` runs `ros2 launch uav_nav gps_goto.launch.py` inside the container with the default
config. To pass launch arguments or open a shell in the container:

```bash
docker run --rm -it --net=host -e ROS_DOMAIN_ID=42 \
  -v ~/coding/ros2_ws/src/uav_nav:/ws/src/uav_nav:ro uav_nav_foxy bash
# inside:
source /opt/ros/foxy/setup.bash
colcon build --packages-select uav_nav --build-base /tmp/build --install-base /tmp/install
source /tmp/install/setup.bash
ros2 launch uav_nav gps_goto.launch.py config:=gps_goto_ntut.yaml
```

## 4. Results (2026-10-26)

| Run | Result |
|---|---|
| Unit tests on Foxy | 19/19 passed (Python 3.8.10, MAVROS 2.4.0) |
| 1 waypoint | error after hold **0.22 m** (Humble: 0.29 m) |
| A → B → C | 0.28 / 0.33 / 0.42 m |
| GPS loss | node detects `fix_type=0` → LAND; PX4 failsafe; landed and disarmed |
| NTUT field, 3 waypoints | 0.36 / 0.16 / 0.01 m |

Logs: `results/foxy/`, `results/ntut/`. Index: [`results/README.md`](../results/README.md).

## 5. Foxy problems found and fixed

Static checks (imports, syntax) had passed before; both problems only appeared when actually flying.

### 5.1 MAVROS 2.4.0 ships ROS 1 launch files

Symptom (`results/foxy/sitl_test_20261026_192943_launch_fail/gps_goto.log`):

```
launch.invalid_launch_file_error.InvalidLaunchFileError: The launch file may have a syntax error, or its format is unknown
```

Cause: `gps_goto.launch.py` included MAVROS' `px4.launch`. In `ros-foxy-mavros` 2.4.0 that file
and `node.launch` are still in ROS 1 syntax, and the PX4 YAML files have no `ros__parameters`:

```
px4.launch  -> Unknown substitution: find               ($(find mavros))
node.launch -> Attribute exec of type <class 'str'> not found in Entity node   (type=, <rosparam>)
```

Fix: the launch file now starts `mavros_node` directly (`mavros_node()` in `launch/gps_goto.launch.py`).
MAVROS' `px4_pluginlists.yaml` / `px4_config.yaml` are passed only when they are in ROS 2 format
(Humble 2.15.1). On Foxy a `plugin_denylist` is set instead; without it the `odometry` plugin
printed a TF error 30 times per second (3 523 lines in one flight).

### 5.2 MAVROS 2.4.0 publishes gp_origin in ECEF

Symptom (`results/foxy/sitl_test_20261026_193306_ecef_origin_bug/`): the flight "succeeded"
(landed and disarmed) but the drone never reached the waypoint:

```
Projection origin: gp_origin (4277582.3507339, 642769.5144400)
WP1 ... distance 7694943.2 m
Takeoff ... wp_timeout -> LAND
```

Cause: `/mavros/global_position/gp_origin` carries **ECEF x/y/z in metres** in the
latitude/longitude/altitude fields on MAVROS 2.4.0, but WGS84 degrees on 2.15.1.
Check: the SITL home (47.3977°, 8.5456°, 488 m) in ECEF is x ≈ 4 277 600 m, y ≈ 642 700 m,
which matches the logged values.

Fix: `geo.origin_lat_lon()` treats a latitude outside ±90° as ECEF and converts it with
`geo.ecef_to_geodetic()` (WGS84). The node logs the raw values so this is visible:
`gp_origin (47.3977472, 8.5455928) converted from ECEF (4277582.5, 642769.3, 4672204.0)`.
Unit tests: `test_ecef_roundtrip`, `test_origin_from_foxy_mavros_ecef`, `test_origin_lat_lon_passthrough`.

**This matters on the drone**: VOXL 2 uses the same MAVROS 2.4.0, so without the fix the real
drone would fly towards a point thousands of km away until `wp_timeout`.

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `docker: command not found` | Step 1 |
| `permission denied while trying to connect to the docker API` | Not in the `docker` group yet: log out/in, or use `sg docker -c "..."` |
| `No uav_nav_foxy image: run docker/foxy/foxy_test.sh first` | Step 2 |
| `PX4 not ready` with `gz_bridge: Service call timed out` in `px4.log` | Gazebo was slow to start (seen once on the first run after boot). Run again |
| Waypoint distance of millions of metres | You are running code from before the ECEF fix (5.2) |
| Many `ODOM: Ex: Could not find a connection between 'map' and 'base_link_frd'` | Code from before the launch fix (5.1) |
