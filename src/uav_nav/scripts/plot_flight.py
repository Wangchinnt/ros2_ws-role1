#!/usr/bin/env python3
"""
Plot the trajectory of a SITL flight from flight.ulg + gps_goto.log in a results directory.

Usage:  python3 plot_flight.py <results dir> [<another dir> ...]
Output: <dir>/flight.png  (left: top-down view, right: altitude over time)

- Trajectory comes from the vehicle_local_position topic in the ulog (PX4 NED).
- Waypoints come from the "WPi GPS (...) -> ENU (E x, N y, U z)" lines in the node log.
  MAVROS only converts NED <-> ENU with the same origin, so E = y_ned, N = x_ned, U = -z_ned.
"""
import os
import re
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from pyulog import ULog  # noqa: E402

WP_RE = re.compile(r'WP(\d+) GPS \(([\d.]+), ([\d.]+), \+([\d.]+) m\) -> ENU '
                   r'\(E (-?[\d.]+), N (-?[\d.]+), U (-?[\d.]+)\)')
RADIUS_RE = re.compile(r'radius ([\d.]+) m')


def load(result_dir):
    ulog = ULog(os.path.join(result_dir, 'flight.ulg'),
                ['vehicle_local_position', 'vehicle_status'])
    lp = ulog.get_dataset('vehicle_local_position').data
    # PX4 SITL logs from boot -> use arm time (arming_state == 2) as t = 0.
    st = ulog.get_dataset('vehicle_status').data
    armed = [ts for ts, a in zip(st['timestamp'], st['arming_state']) if a == 2]
    t0 = int(armed[0]) if armed else int(lp['timestamp'][0])
    t = [(int(ts) - t0) / 1e6 for ts in lp['timestamp']]
    north, east, up = lp['x'], lp['y'], -lp['z']

    wps, radius = [], 1.0
    with open(os.path.join(result_dir, 'gps_goto.log'), encoding='utf-8') as f:
        for line in f:
            m = WP_RE.search(line)
            if m:
                wps.append((int(m.group(1)), float(m.group(5)), float(m.group(6)),
                            float(m.group(7))))
            r = RADIUS_RE.search(line)
            if r:
                radius = float(r.group(1))
    return t, north, east, up, wps, radius


def plot(result_dir):
    t, north, east, up, wps, radius = load(result_dir)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5),
                                   gridspec_kw={'width_ratios': [1.1, 1]})

    ax1.plot(east, north, color='#2F6FB0', lw=1.8, label='trajectory (EKF)')
    ax1.plot(east[0], north[0], 'o', color='#14213D', ms=8, label='takeoff')
    for i, e, n, _ in wps:
        ax1.add_patch(plt.Circle((e, n), radius, fill=False, ls='--', color='#B5540B'))
        ax1.plot(e, n, 'x', color='#B5540B', ms=10, mew=2.5)
        ax1.annotate('WP%d' % i, (e, n), textcoords='offset points', xytext=(8, 8),
                     color='#B5540B', fontsize=11, fontweight='bold')
    ax1.set_xlabel('East (m)')
    ax1.set_ylabel('North (m)')
    ax1.set_title('Top-down view (dashed circle = %.1f m radius)' % radius)
    ax1.set_aspect('equal', adjustable='datalim')
    ax1.grid(alpha=0.3)
    ax1.legend(loc='best')

    ax2.plot(t, up, color='#2F6FB0', lw=1.8, label='altitude (EKF)')
    ax2.axvline(0, color='#14213D', lw=1, ls=':')
    ax2.annotate('arm', (0, max(up) * 0.5), textcoords='offset points', xytext=(4, 0),
                 color='#14213D', fontsize=10)
    for i, _, _, u in wps:
        ax2.axhline(u, ls='--', color='#B5540B', lw=1)
        ax2.annotate('WP%d' % i, (t[-1], u), textcoords='offset points', xytext=(-30, 4),
                     color='#B5540B', fontsize=10)
    ax2.set_xlabel('Time since arm (s); before 0 = waiting on the ground')
    ax2.set_ylabel('Altitude above origin (m)')
    ax2.set_title('Altitude over time')
    ax2.grid(alpha=0.3)

    fig.suptitle(os.path.basename(os.path.normpath(result_dir)), fontsize=11, color='#4A5568')
    fig.tight_layout()
    out = os.path.join(result_dir, 'flight.png')
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(out)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for d in sys.argv[1:]:
        plot(d)
