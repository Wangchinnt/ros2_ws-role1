# Field test plan: NTUT East Dorm sports field

First outdoor flights of `gps_goto` on the Starling 2 Max. Each step must pass before the next one.
The mission is the same one flown in SITL (`config/gps_goto_ntut.yaml`, `results/report2_2026-10-26/ntut/`).

## Site

| | |
|---|---|
| Place | NTUT East Dorm sports field, Taipei |
| Takeoff point (SITL) | 25.042486, 121.537627 (centroid of the waypoints, inside the field) |
| WP1 | 25.042833, 121.537612 (~39 m N of takeoff) |
| WP2 | 25.042224, 121.537790 (~29 m S, ~17 m E) |
| WP3 | 25.042400, 121.537478 (~10 m S, ~15 m W) |
| Legs | WP1→WP2 70.1 m, WP2→WP3 37.0 m, WP3→WP1 50.0 m |
| Altitude | 10 m above takeoff (dorm buildings around the field are taller: stay inside the field) |

Re-measure the waypoints on site (e.g. with the drone's own GPS at each corner) if the field
marks differ from the map, and update a copy of the config file.

## Weather limits

| Condition | Limit for these first flights |
|---|---|
| Mean wind | **≤ 3 m/s** (SITL verified the logic at 3 m/s: error after hold 0.75–1.86 m) |
| Gusts | ≤ 5 m/s |
| Rain | none |

Taipei's prevailing wind in autumn is from the east/north-east (NE monsoon) at a few m/s
[not verified against official data; check the CWA observation for Taipei on the day:
<https://www.cwa.gov.tw/> (Observation → Taipei)].
The SITL wind model is not calibrated (at 5 m/s from ENE the simulation could not take off,
`results/report2_2026-10-26/ntut/…_wind-4.6_-1.9`), so it cannot predict the real drone's wind tolerance; the limits
above are conservative choices for a first test.

## Before going to the field

- [ ] Code version includes the Foxy fixes (`git log` shows the ECEF/launch fix commit).
- [ ] Bench test done ([DEPLOY_VOXL2.md §5](DEPLOY_VOXL2.md#5-bench-test-props-off)): connection, GPS fix, origin conversion.
- [ ] Answers to the questions in [DEPLOY_VOXL2.md §3](DEPLOY_VOXL2.md#3-questions-for-role-4-answers-needed-before-the-first-flight).
- [ ] Batteries charged (drone + RC + laptop).
- [ ] Note the current values of every PX4 parameter you plan to change: PX4 saves `param set` to disk.

## On site, before each flight

- [ ] Field clear of people; one spotter.
- [ ] RC pilot ready, knows the takeover switch (Position mode).
- [ ] QGroundControl connected, shows GPS fix 3D, satellites ≥ 10, `h_acc` < `max_eph`.
- [ ] Wind within limits.
- [ ] `ros2 topic echo --once /mavros/state` → `connected: true`.

## Steps

| # | Test | Command / action | Pass when |
|---|---|---|---|
| 1 | Manual hover | Pilot: takeoff in Position mode, hover 30 s, land | Stable hover; note GPS `h_acc` |
| 2 | Offboard hold | `waypoint_frame:=offset waypoints:="[0, 0, 5]"` (above takeoff, 5 m) | Takes off, holds within ~2 m, lands |
| 3 | One short leg | `waypoint_frame:=offset waypoints:="[10, 0, 5]"` (10 m North; pick a direction that stays in the field) | `REACHED WP1`, error after hold < 2 m, lands |
| 4 | NTUT mission | `config:=gps_goto_ntut.yaml` | All 3 waypoints reached, lands |

Every command is `ros2 launch uav_nav gps_goto.launch.py fcu_url:=<FCU_URL> <arguments above>`;
see [MANUAL_RUN.md §3](MANUAL_RUN.md#choose-the-waypoints-from-the-terminal-no-file-editing). Offsets need
no coordinates, so steps 2–3 work wherever the drone takes off.
| 5 | Pilot takeover (optional) | During step 4, pilot switches to Position mode | Node logs ABORT and stops commanding; pilot lands |

Run each step at least twice. Stop the session if any step fails, and analyse the logs first.

## Abort criteria (pilot takes over immediately)

- Drone moves away from the expected direction, or climbs above ~15 m.
- Oscillation, or the drone does not hold position after takeoff.
- GPS warning in QGC, or loss of the telemetry link.
- Anyone enters the field.

## Data to collect after each flight

| What | Where |
|---|---|
| Node + MAVROS log | redirect the launch: `ros2 launch ... 2>&1 \| tee gps_goto.log` |
| PX4 flight log (`.ulg`) | QGC → Analyze Tools → Log Download, or `/data/px4/log/` on the VOXL 2 (❓ path to confirm) |
| Wind, time, notes | written down on site |

Put them in `results/field_<date>_<step>/` and plot with
`python3 src/uav_nav/scripts/plot_flight.py results/field_<date>_<step>` (needs `flight.ulg` in that directory).
Compare with the SITL results in `results/report2_2026-10-26/ntut/`.
