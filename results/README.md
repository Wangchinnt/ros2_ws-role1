# results: SITL flight logs

Each `sitl_test_<date>_<time>[_<label>]/` directory is one flight and contains:

| File | What it is |
|---|---|
| `gps_goto.log` | launch log: the `gps_goto` node, MAVROS (and `mavlink-routerd` if used) |
| `px4.log` | PX4 SITL log (commander, failsafe, ...) |
| `flight.ulg` | PX4 binary flight log, open with `pyulog` / PlotJuggler / Flight Review. **Not in git** (too large, ~300 MB total) |
| `flight.png` | trajectory plot, made by `src/uav_nav/scripts/plot_flight.py` |
| `summary.txt` | summary: node state transitions, PX4 events, conclusion |

Older directories (before 2026-09-28 01:54) only have `gps_goto.log` and `px4.log`.

Node log messages were originally in Vietnamese; the recorded logs have been translated with the same wording the current code prints, so the scripts' `grep` patterns work on both. Numbers are untouched.

## Index (2026-09-28)

| Directory | Content | Main result |
|---|---|---|
| `mavlink/milestone1_20260928_015716/` | **Milestone 1**: 5 consecutive flights, 1 waypoint | **5/5 passed**, error after hold 0.22–0.27 m (`SUMMARY.md`) |
| `mavlink/sitl_test_20260928_022808_abc/` | A → B → C, final code | error after hold 0.40 / 0.30 / 0.30 m; `flight.png` used in the report |
| `mavlink/sitl_test_20260928_015406_router/` | Flight through **mavlink-router** (like `voxl-mavlink-server`) | error after hold 0.30 m; router forwarded 18 548 msgs PX4 → MAVROS, 1 220 msgs MAVROS → PX4 |
| `mavlink/sitl_test_20260928_0123*..012752_abc` | First 4 MAVLink flights | 012356 had no gp_origin yet (used the fallback origin) |
| `failsafe/…_kill_node` | Node killed mid-flight | PX4 failsafe, auto-land, disarmed at 27.9 s |
| `failsafe/…_mode_switch` | Switched to AUTO.LOITER (pilot takeover) | node ABORTs, PX4 holds position; test script commands land |
| `failsafe/…_gps_loss` | `SIM_GPS_USED=0` mid-flight | node requests AUTO.LAND, PX4 failsafe DESCEND, disarmed at 27.2 s |
| `wind/…_wind0_0`, `…_wind3_0` | Windy world (0 and 3 m/s towards East, with noise) | reached target; error after hold 1.26 m and 1.60 m |
| `wind/…_wind6_0` | 6 m/s wind | drone pushed along the ground, cannot take off → node takeoff timeout → land. **Wind model is not calibrated, does not reflect the real drone** |
| `wind/…_wind6_0_driftcheck` | 6 m/s wind, after adding the `max_drift` horizontal drift check | node detects 3.1 m drift after 3.7 s → land |
| `mavlink/sitl_test_20260928_035656_abc_v2/` | A → B → C after the `max_drift` + `DISARM` changes | error after hold 0.37 / 0.25 / 0.31 m |
| `wind/invalid_gps_param/` | **Invalid**: run while `SIM_GPS_USED=0` was still persisted from the `gps_loss` test | PX4 never reports "Ready for takeoff". Kept as a lesson: PX4 saves params to disk, so `sitl_test.sh` now resets `SIM_GPS_USED=10` on startup |
| `xrce_dds/` | Old version over uXRCE-DDS (`px4_msgs`) | error on arrival 0.58–0.92 m |

## Index (2026-10-26): ROS 2 Foxy and the NTUT field

Foxy runs use `FOXY=1` (MAVROS 2.4.0 + gps_goto in Docker, see [`docs/FOXY_DOCKER.md`](../docs/FOXY_DOCKER.md)).
NTUT runs use `SIM_HOME="25.042486 121.537627 10"` and `config:=gps_goto_ntut.yaml`.

| Directory | Content | Main result |
|---|---|---|
| `foxy/unit_20261026_192130/` | `docker/foxy/foxy_test.sh`: build + unit tests on Foxy | 19/19 passed, Python 3.8.10, MAVROS 2.4.0 |
| `foxy/…_192943_launch_fail/` | **Bug 1**: first Foxy flight | launch failed: MAVROS 2.4.0 `px4.launch` is ROS 1 format; drone never armed |
| `foxy/…_193306_ecef_origin_bug/` | **Bug 2**: after fixing the launch | `gp_origin` read as lat/lon but is ECEF → WP1 "7 694 943 m" away, takeoff timeout → land |
| `foxy/sitl_test_20261026_193704/` | 1 waypoint, both bugs fixed | error after hold 0.22 m |
| `foxy/…_193926_abc/` | A → B → C on Foxy | 0.28 / 0.33 / 0.42 m |
| `foxy/…_194046_gps_loss/` | GPS loss on Foxy | node → LAND, PX4 failsafe, landed and disarmed |
| `mavlink/…_193822_humble_after_launch_change/` | Humble regression after the launch change | 0.29 m |
| `ntut/sitl_test_20261026_194544/` | NTUT field, Humble | 0.30 / 0.14 / 0.11 m |
| `ntut/…_194735_foxy/` | NTUT field, Foxy | 0.36 / 0.16 / 0.01 m |
| `ntut/…_194905_wind-3_0/` | NTUT field, 3 m/s wind **from** the East (`WIND="-3 0"`) | 0.75 / 0.94 / 1.86 m; path bends West on the leg to WP1 (`flight.png`) |
| `ntut/…_195030_wind-4.6_-1.9/` | NTUT field, 5 m/s from ENE | simulation slowed down (timesync RTT up to 2.3 s), takeoff timeout → land. Wind model limit, not a node result |
| `ntut/…_195933_foxy_after_wp_check/` | NTUT field, Foxy, after adding `max_wp_distance` / `max_alt` | 0.33 / 0.22 / 0.14 m |
| `ntut/…_200500_wrong_waypoint_abort/` | Taipei home + default (Zurich) waypoint | `WP1 is 9548205 m away (> max_wp_distance 500 m) -> ABORT`, drone never armed |
| `ntut/…_204927_default_1wp/` | Plain `sitl_test.sh` after NTUT became the default (home + `gps_goto.yaml`) | error after hold 0.32 m |

"Error on arrival" = GPS distance to the target when the drone first enters the 1 m acceptance radius.
"Error after hold" = after holding position for `hold_time` seconds; this is the real accuracy.

Re-plot: `python3 src/uav_nav/scripts/plot_flight.py results/<dir>`
