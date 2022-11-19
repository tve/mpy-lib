# geo.py - Simplified geographic coordinate calculations
# Copyright © 2022 by Thorsten von Eicken.

import math


class Coord:
    # Create coordinates passing either tuple (degrees,minutes), or tuple (degrees,minutes*1E6),
    # or float degrees
    def __init__(self, lat, lon):
        if isinstance(lat, tuple):
            self.lat = (lat[0], lat[1] if isinstance(lat[1], int) else round(lat[1]*16666.6666))
            self.lon = (lon[0], lon[1] if isinstance(lon[1], int) else round(lon[1]*16666.6666))
        else:
            self.lat = (int(lat), int((lat-int(lat))*1000000))
            self.lon = (int(lon), int((lon-int(lon))*1000000))

    def float(self):
        return (self.lat[0]+self.lat[1]/1000000.0, self.lon[0]+self.lon[1]/1000000.0)

    def __str__(self):
        return "(%d.%06d,%d.%06d)" % (self.lat[0], abs(self.lat[1]), self.lon[0], abs(self.lon[1]))

    # Flat-surface distance to another coordinate in meters
    # From https://en.wikipedia.org/wiki/Geographical_distance "Ellipsoidal Earth proj. to a plane"
    # Error is negligible for GPS coords for distances of a few km
    def approx_distance(self, coord2):
        dlon = (coord2.lon[0] - self.lon[0]) + (coord2.lon[1] - self.lon[1]) / 1000000
        dlat = (coord2.lat[0] - self.lat[0]) + (coord2.lat[1] - self.lat[1]) / 1000000
        lat = (self.lat[0] + coord2.lat[0]) / 2  # ignore fractions
        x = math.radians(dlon) * math.cos(math.radians(lat))
        y = math.radians(dlat)
        return round(math.sqrt(x * x + y * y) * 6371000)

    # Bearing to another coordinate in degrees
    # From https://www.movable-type.co.uk/scripts/latlong.html
    # Error is up to 5-6 degrees at lat 34 for dist up to a few km
    def approx_bearing(self, coord2):
        dlon = (coord2.lon[0] - self.lon[0]) + (coord2.lon[1] - self.lon[1]) / 1000000
        dlat = (coord2.lat[0] - self.lat[0]) + (coord2.lat[1] - self.lat[1]) / 1000000
        lat = (self.lat[0] + coord2.lat[0]) / 2  # ignore fractions
        return int(math.degrees(math.atan2(dlon * math.cos(math.radians(lat)), dlat))) % 360

    # Distance and bearing as above returned as a tuple
    def approx_dist_bearing(self, coord2):
        dlon = (coord2.lon[0] - self.lon[0]) + (coord2.lon[1] - self.lon[1]) / 1000000
        dlat = (coord2.lat[0] - self.lat[0]) + (coord2.lat[1] - self.lat[1]) / 1000000
        lat = (self.lat[0] + coord2.lat[0]) / 2  # ignore fractions
        x = math.radians(dlon) * math.cos(math.radians(lat))
        y = math.radians(dlat)
        return (round(math.sqrt(x * x + y * y) * 6371000), int(math.degrees(math.atan2(x, y))) % 360)
