# Running everything by hand

Every step in one terminal command, so you can see what each piece does.
The only scripts left are `sitl_test.sh` (the same steps, automated, to re-check the code after a change),
`docker/foxy/foxy_test.sh` (build the Foxy image + unit tests) and `plot_flight.py` (draw a flight).

Paths assume `~/coding/tools/PX4-Autopilot` (PX4 v1.14) and `~/coding/ros2_ws` (this repo).

## 0. Build (after every code change)

```bash
cd ~/coding/ros2_ws
source /opt/ros/humble/setup.bash
source ~/coding/tools/mavros_ws/install/setup.bash     # MAVROS built from source
colcon build --symlink-install
source install/setup.bash                              # in every new terminal
colcon test --packages-select uav_nav && colcon test-result   # optional: unit tests + lint
```

## 1. Terminals

| Terminal | Runs | Stop with |
|---|---|---|
| T1 | PX4 SITL + Gazebo | `Ctrl+C` (or type `shutdown` at `pxh>`) |
| T2 | QGroundControl (optional, map + mode display) | close the window |
| T3 | MAVROS + `gps_goto` (`ros2 launch`) | ends by itself after landing, or `Ctrl+C` |
| T4 | watching topics (optional) | `Ctrl+C` |

Only one PX4 can run at a time: a second one prints `PX4 server already running for instance 0` and stops.

## 2. Put the simulated drone at the NTUT field (once)

PX4 places the simulated GPS at the parameters `SIM_GZ_HOME_LAT/LON/ALT`. It reads them **only when it
starts**, and it **saves** every `param set` to disk (`build/px4_sitl_default/rootfs/parameters.bson`),
so you set them once and restart PX4.

```bash
# T1
cd ~/coding/tools/PX4-Autopilot && make px4_sitl gz_x500
```

Wait for `Ready for takeoff!`, then type at the `pxh>` prompt:

```
param set SIM_GZ_HOME_LAT 25.042486
param set SIM_GZ_HOME_LON 121.537627
param set SIM_GZ_HOME_ALT 10
```

Stop PX4 (`Ctrl+C`) and start it again with the same `make` command. Check:

```
pxh> param show SIM_GZ_HOME_LAT
x + SIM_GZ_HOME_LAT [874,1384] : 25.0425          (PX4 prints 4 decimals)
```

From now on every PX4 start is at the NTUT field (25.042486, 121.537627: the centre of the three
waypoints, inside the field). Repeat this step only after deleting PX4's `parameters.bson` or rebuilding PX4 from scratch.

If the home and the waypoints do not match (e.g. a typo in a coordinate, or PX4 started before step 2), the node refuses to fly:
`WP1 is 9548205 m away (> max_wp_distance 500 m) -> ABORT`, and the drone never arms.

## 3. Fly

```bash
# T1: PX4 + Gazebo (GUI). Wait for "Ready for takeoff!"
cd ~/coding/tools/PX4-Autopilot && make px4_sitl gz_x500

# T2 (optional): QGroundControl connects by itself on UDP 14550
~/Applications/QGroundControl-v5.0.8-x86_64.AppImage

# T3: MAVROS + gps_goto (source the workspace first, step 0)
ros2 launch uav_nav gps_goto.launch.py config:=gps_goto_ntut.yaml      # 3 waypoints on the field
```

A good flight prints (from `results/report2_2026-10-26/video/video_20261026_233608_ntut_nowind/gps_goto.log`):

```
After holding 3 s at WP1: error 0.18 m from target
After holding 3 s at WP2: error 0.11 m from target
After holding 3 s at WP3: error 0.21 m from target
Landed and disarmed. Done.
```

### Choose the waypoints from the terminal (no file editing)

The `waypoints` argument overrides the config file. Keep the quotes.

```bash
# GPS coordinates: [lat, lon, alt_rel, lat, lon, alt_rel, ...]; alt_rel = metres above the takeoff point
ros2 launch uav_nav gps_goto.launch.py waypoints:="[25.042224, 121.537790, 8.0]"

# Offsets from the takeoff point, no coordinates needed: [north_m, east_m, alt_rel, ...]
ros2 launch uav_nav gps_goto.launch.py waypoint_frame:=offset waypoints:="[10, 0, 5]"          # 10 m North, 5 m up
ros2 launch uav_nav gps_goto.launch.py waypoint_frame:=offset waypoints:="[0, 0, 3]"           # hold above takeoff at 3 m
ros2 launch uav_nav gps_goto.launch.py waypoint_frame:=offset waypoints:="[10, 0, 5, 10, 10, 5, 0, 0, 5]"   # small square
```

Any other node parameter can be changed the same way by editing a copy of a config file
(`acceptance_radius`, `takeoff_alt`, `hold_time`, `max_wp_distance`, ...; see the README table).

GPS override, as printed in SITL (`results/runs`, 2026-10-26):

```
WP1 GPS (25.0422240, 121.5377900, +8.0 m) -> ENU (E 30.75, N -19.57, U 7.92), distance 36.5 m
After holding 5 s at WP1: error 0.62 m from target
```

Offset mode prints one line per waypoint with the equivalent GPS point (format from the code and the
unit tests; not yet flown in SITL):

```
Waypoints are offsets from takeoff (North, East, Up)
WP1 offset (N +10.0, E +0.0, +5.0 m) ~ GPS (25.0..., 121.5...), distance 10.0 m
```

**Getting a coordinate on the real field**: put the drone (or walk with it) on the spot and read its GPS:

```bash
ros2 topic echo --once /mavros/global_position/global     # latitude, longitude
```

## 4. Watch while flying (T4)

```bash
ros2 topic echo /mavros/state --field mode                    # OFFBOARD, AUTO.LAND, ...
ros2 topic hz /mavros/setpoint_position/local                 # ~20 Hz (PX4 needs > 2 Hz)
ros2 topic echo /mavros/gpsstatus/gps1/raw --field h_acc      # GPS accuracy in mm
rqt_graph                                                     # gps_goto <-> mavros
```

## 5. Faults, by hand

| Fault | How | Expected |
|---|---|---|
| GPS loss | T1 `pxh>`: `param set SIM_GPS_USED 0` | node: `GPS degraded ... -> LAND`; PX4 failsafe; lands |
| | **then restore**: `param set SIM_GPS_USED 10` (saved to disk!) | |
| Pilot takeover | QGC: click the mode name at the top → Hold | node: `Lost Offboard ... -> ABORT`, stops commanding |
| Companion computer dies | T3: `Ctrl+C` | PX4: no setpoints for `COM_OF_LOSS_T` (1 s) → failsafe → lands |

## 6. Wind, by hand

Start Gazebo with the windy world **before** PX4; PX4 then uses the running world.

```bash
# T1a: windy world. Edit the two numbers: air velocity East, North in m/s ("-3 0" = 3 m/s from the East)
cd ~/coding/ros2_ws
sed "s/WIND_E/-3/; s/WIND_N/0/" sim/worlds/windy.sdf.in > /tmp/windy.sdf
export GZ_SIM_RESOURCE_PATH=$PWD/sim/models:$HOME/coding/tools/PX4-Autopilot/Tools/simulation/gz/models:$HOME/coding/tools/PX4-Autopilot/Tools/simulation/gz/worlds
gz sim -r /tmp/windy.sdf

# T1b: PX4, same as before
cd ~/coding/tools/PX4-Autopilot && make px4_sitl gz_x500
```

`sim/models/x500` is PX4's x500 with wind enabled; putting `sim/models` first in the path makes Gazebo use it.
The wind model is not calibrated: from ~5 m/s the simulation itself breaks down.

## 7. Foxy (like the VOXL 2)

See [FOXY_DOCKER.md](FOXY_DOCKER.md): build the image once (`bash docker/foxy/foxy_test.sh`),
then run T3 inside the container instead of on the host.

## 8. Plot a flight

PX4 writes a `.ulg` per flight under `~/coding/tools/PX4-Autopilot/build/px4_sitl_default/rootfs/log/<date>/`.

```bash
mkdir -p ~/coding/ros2_ws/results/runs/my_flight
cp "$(ls -t ~/coding/tools/PX4-Autopilot/build/px4_sitl_default/rootfs/log/*/*.ulg | head -1)" \
   ~/coding/ros2_ws/results/runs/my_flight/flight.ulg
python3 ~/coding/ros2_ws/src/uav_nav/scripts/plot_flight.py ~/coding/ros2_ws/results/runs/my_flight
xdg-open ~/coding/ros2_ws/results/runs/my_flight/flight.png
```

`results/runs/` is not in git. Move a run you want to keep into `results/<report>/`.

## 9. Stop everything

`Ctrl+C` in each terminal. If something is left over:

```bash
pkill -INT -x px4; pkill -f "gz sim"; pkill -x QGroundControl
```

## 10. On the real drone

Same launch, plus the MAVLink address of the drone (see [DEPLOY_VOXL2.md](DEPLOY_VOXL2.md)):

```bash
ros2 launch uav_nav gps_goto.launch.py fcu_url:=<FCU_URL> waypoint_frame:=offset waypoints:="[0, 0, 3]"
ros2 launch uav_nav gps_goto.launch.py fcu_url:=<FCU_URL> config:=gps_goto_ntut.yaml
```
