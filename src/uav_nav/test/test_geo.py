import math
from types import SimpleNamespace

from uav_nav.geo import (ecef_to_geodetic, geodetic_to_ecef, haversine, MapProjection,
                         origin_lat_lon)

HOME = (47.397742, 8.545594)  # SIM_GZ_HOME_LAT/LON of PX4 SITL


def test_origin_is_zero():
    p = MapProjection(*HOME)
    x, y = p.project(*HOME)
    assert abs(x) < 1e-9 and abs(y) < 1e-9


def test_north_only():
    # 0.001 deg latitude = R * pi/180 * 0.001 = 111.195 m, due North, East = 0
    p = MapProjection(*HOME)
    x, y = p.project(HOME[0] + 0.001, HOME[1])
    assert abs(x - 111.195) < 0.01
    assert abs(y) < 0.01


def test_east_is_positive():
    p = MapProjection(*HOME)
    x, y = p.project(HOME[0], HOME[1] + 0.001)
    assert y > 0
    assert abs(y - 111.195 * math.cos(math.radians(HOME[0]))) < 0.1


def test_distance_matches_haversine():
    # Error < 0.1 m within a few km radius (Phase 6 requirement)
    p = MapProjection(*HOME)
    for dlat, dlon in [(0.00046, 0.00061), (-0.01, 0.02), (0.02, -0.015)]:
        lat, lon = HOME[0] + dlat, HOME[1] + dlon
        x, y = p.project(lat, lon)
        assert abs(math.hypot(x, y) - haversine(HOME[0], HOME[1], lat, lon)) < 0.1


def test_round_trip():
    p = MapProjection(*HOME)
    for n, e in [(50.0, 45.0), (-300.0, 1200.0), (2000.0, -1500.0)]:
        lat, lon = p.reproject(n, e)
        x, y = p.project(lat, lon)
        assert abs(x - n) < 1e-6 and abs(y - e) < 1e-6


def test_ecef_roundtrip():
    lat, lon, alt = ecef_to_geodetic(*geodetic_to_ecef(HOME[0], HOME[1], 488.0))
    assert abs(lat - HOME[0]) < 1e-9 and abs(lon - HOME[1]) < 1e-9 and abs(alt - 488.0) < 1e-3


def test_origin_from_foxy_mavros_ecef():
    # MAVROS 2.4.0 (Foxy) puts ECEF x/y/z into gp_origin's latitude/longitude/altitude
    x, y, z = geodetic_to_ecef(HOME[0], HOME[1], 488.0)
    lat, lon, was_ecef = origin_lat_lon(SimpleNamespace(latitude=x, longitude=y, altitude=z))
    assert was_ecef
    assert haversine(lat, lon, *HOME) < 0.01


def test_origin_lat_lon_passthrough():
    p = SimpleNamespace(latitude=HOME[0], longitude=HOME[1], altitude=488.0)
    assert origin_lat_lon(p) == (HOME[0], HOME[1], False)
