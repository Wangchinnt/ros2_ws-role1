"""
GPS (lat/lon) <-> local NED, using the same formulas as PX4.

Port of MapProjection::project / reproject from
PX4-Autopilot/src/lib/geo/geo.cpp (azimuthal equidistant projection).
Using exactly this formula makes our computed targets match how the PX4 EKF
places its NED origin (ref_lat, ref_lon in VehicleLocalPosition).
"""
import math

EARTH_RADIUS = 6371000.0  # m, CONSTANTS_RADIUS_OF_EARTH in geo.h


class MapProjection(object):

    def __init__(self, ref_lat, ref_lon):
        self.ref_lat = math.radians(ref_lat)
        self.ref_lon = math.radians(ref_lon)
        self.ref_sin_lat = math.sin(self.ref_lat)
        self.ref_cos_lat = math.cos(self.ref_lat)

    def project(self, lat, lon):
        """Return (north, east) in meters relative to the origin."""
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        sin_lat = math.sin(lat_rad)
        cos_lat = math.cos(lat_rad)
        cos_d_lon = math.cos(lon_rad - self.ref_lon)

        arg = self.ref_sin_lat * sin_lat + self.ref_cos_lat * cos_lat * cos_d_lon
        arg = max(-1.0, min(1.0, arg))
        c = math.acos(arg)
        k = c / math.sin(c) if abs(c) > 0 else 1.0

        x = k * (self.ref_cos_lat * sin_lat - self.ref_sin_lat * cos_lat * cos_d_lon) \
            * EARTH_RADIUS
        y = k * cos_lat * math.sin(lon_rad - self.ref_lon) * EARTH_RADIUS
        return x, y

    def reproject(self, x, y):
        """Inverse: (north, east) meters -> (lat, lon) degrees."""
        x_rad = x / EARTH_RADIUS
        y_rad = y / EARTH_RADIUS
        c = math.sqrt(x_rad * x_rad + y_rad * y_rad)
        if c == 0:
            return math.degrees(self.ref_lat), math.degrees(self.ref_lon)
        sin_c = math.sin(c)
        cos_c = math.cos(c)
        lat_rad = math.asin(cos_c * self.ref_sin_lat + (x_rad * sin_c * self.ref_cos_lat) / c)
        lon_rad = self.ref_lon + math.atan2(
            y_rad * sin_c, c * self.ref_cos_lat * cos_c - x_rad * self.ref_sin_lat * sin_c)
        return math.degrees(lat_rad), math.degrees(lon_rad)


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance between two GPS points (m), used as a cross-check."""
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS * math.asin(math.sqrt(a))
