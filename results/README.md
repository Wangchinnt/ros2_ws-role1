# results: SITL flight logs

```
results/
├── report1_2026-09-28/   flown at PX4's default SITL location (Zurich), ROS 2 Humble
├── report2_2026-10-26/   ROS 2 Foxy (Docker) and the NTUT East Dorm field
└── runs/                 where sitl_test.sh writes new runs; not in git. Move a run you want to keep into a report folder
```

Each run directory is one flight:

| File | What it is |
|---|---|
| `gps_goto.log` | launch log: the `gps_goto` node, MAVROS (and `mavlink-routerd` if used) |
| `px4.log` | PX4 SITL log (commander, failsafe, ...) |
| `flight.ulg` | PX4 binary flight log (pyulog / PlotJuggler / Flight Review). **Not in git** (~10 MB each) |
| `flight.png` | trajectory plot: `python3 src/uav_nav/scripts/plot_flight.py results/<dir>` (needs `flight.ulg`) |
| `summary.txt` | node state transitions, PX4 events, conclusion |

"Error on arrival" = GPS distance to the target when the drone first enters the acceptance radius.
"Error after hold" = after holding position for `hold_time` seconds; this is the real accuracy.

## Report 2 (2026-10-26): Foxy and the NTUT field

Foxy runs: MAVROS 2.4.0 + gps_goto in Docker ([`docs/FOXY_DOCKER.md`](../docs/FOXY_DOCKER.md)).
NTUT runs: SITL home 25.042486, 121.537627 ([`docs/MANUAL_RUN.md`](../docs/MANUAL_RUN.md) §2).

| Directory (in `report2_2026-10-26/`) | Content | Main result |
|---|---|---|
| `foxy/unit_20261026_192130/` | `docker/foxy/foxy_test.sh`: build + unit tests on Foxy | passed, Python 3.8.10, MAVROS 2.4.0 |
| `foxy/…_192943_launch_fail/` | **Bug 1**: first Foxy flight | launch failed: MAVROS 2.4.0 `px4.launch` is ROS 1 format; never armed |
| `foxy/…_193306_ecef_origin_bug/` | **Bug 2**: after fixing the launch | `gp_origin` read as lat/lon but is ECEF → WP1 "7 694 943 m" away, takeoff timeout → land |
| `foxy/sitl_test_20261026_193704/` | 1 waypoint, both bugs fixed (Zurich) | error after hold 0.22 m |
| `foxy/…_193926_abc/` | 3 waypoints on Foxy (Zurich) | 0.28 / 0.33 / 0.42 m |
| `foxy/…_194046_gps_loss/` | GPS loss on Foxy (Zurich) | node → LAND, PX4 failsafe, landed and disarmed |
| `humble/…_193822_humble_after_launch_change/` | Humble regression after the launch change | 0.29 m |
| `ntut/sitl_test_20261026_194544/` | NTUT field, Humble | 0.30 / 0.14 / 0.11 m |
| `ntut/…_194735_foxy/` | NTUT field, Foxy | 0.36 / 0.16 / 0.01 m |
| `ntut/…_194905_wind-3_0/` | NTUT, 3 m/s wind **from** the East | 0.75 / 0.94 / 1.86 m; path bends West on the leg to WP1 (`flight.png`) |
| `ntut/…_195030_wind-4.6_-1.9/` | NTUT, 5 m/s from ENE | simulation slowed down (timesync RTT up to 2.3 s), takeoff timeout → land. Wind model limit, not a node result |
| `ntut/…_195933_foxy_after_wp_check/` | NTUT, Foxy, after adding `max_wp_distance` / `max_alt` | 0.33 / 0.22 / 0.14 m |
| `ntut/…_200500_wrong_waypoint_abort/` | waypoint 9 548 km from the drone | `WP1 is 9548205 m away (> max_wp_distance 500 m) -> ABORT`, never armed |
| `ntut/…_204927_default_1wp/` | default config `gps_goto.yaml` (NTUT WP1) | 0.32 m |
| `ntut/…_222339_terminal_gps_override/` | `waypoints:="[25.042224,121.537790,8.0]"` from the terminal | 0.62 m (SITL home was at WP3 for this run) |
| `video/video_20261026_233608_ntut_nowind/` | Run shown in the screen recording, NTUT field (GUI: Gazebo + PX4 + QGC) | 0.18 / 0.11 / 0.21 m |
| `video/video_20261026_232852_ntut_wind3/` | Run shown in the screen recording, 3 m/s wind from the East | 0.77 / 0.99 / 1.82 m |

## Report 1 (2026-09-28): first SITL results (Zurich, Humble)

| Directory (in `report1_2026-09-28/`) | Content | Main result |
|---|---|---|
| `mavlink/milestone1_20260928_015716/` | **Milestone 1**: 5 consecutive flights, 1 waypoint | **5/5 passed**, error after hold 0.22–0.27 m (`SUMMARY.md`) |
| `mavlink/sitl_test_20260928_022808_abc/` | A → B → C | 0.40 / 0.30 / 0.30 m; `flight.png` used in report 1 |
| `mavlink/sitl_test_20260928_035656_abc_v2/` | A → B → C after the `max_drift` + `DISARM` changes | 0.37 / 0.25 / 0.31 m |
| `mavlink/sitl_test_20260928_015406_router/` | Through **mavlink-router** (like `voxl-mavlink-server`) | 0.30 m; router forwarded 18 548 msgs PX4 → MAVROS, 1 220 back |
| `failsafe/…_kill_node` | Node killed mid-flight | PX4 failsafe, auto-land, disarmed at 27.9 s |
| `failsafe/…_mode_switch` | Switched to AUTO.LOITER (pilot takeover) | node ABORTs, PX4 holds position |
| `failsafe/…_gps_loss` | `SIM_GPS_USED=0` mid-flight | node requests AUTO.LAND, PX4 failsafe DESCEND, disarmed at 27.2 s |
| `wind/…_wind0_0`, `…_wind3_0` | Windy world, 0 and 3 m/s towards East | 1.26 m and 1.60 m |
| `wind/…_wind6_0`, `…_wind6_0_driftcheck` | 6 m/s | cannot take off; with `max_drift` the node lands after 3.7 s |
| `wind/invalid_gps_param/` | **Invalid**: `SIM_GPS_USED=0` was still saved from a gps_loss test | never "Ready for takeoff". Lesson: PX4 saves params to disk |
| `xrce_dds/` | Old version over uXRCE-DDS (`px4_msgs`), replaced by MAVROS | error on arrival 0.58–0.92 m |
| `demo/demo_20260928_033839_main/` | GUI demo of report 1 | |
