from pyproj import Proj
from osgeo import osr

class CoordinateSystem:
    @staticmethod
    def latlon2utm(lon: float, lat: float) -> dict:
        """
        Convert latitude and longitude to UTM coordinates.
        Returns zone, EPSG code, and projected x/y coordinates.
        """
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("Invalid latitude or longitude")

        zone = int(lon // 6) + 31
        proj = Proj(proj="utm", zone=zone, ellps="WGS84")
        x, y = proj(lon, lat)

        if lat < 0:
            y += 10_000_000  # Apply false northing for southern hemisphere

        epsg = 32600 + zone  # EPSG for WGS 84 / UTM zone
        return {"zone": zone, "epsg": epsg, "x": x, "y": y}

    @staticmethod
    def utm2latlon(zone: int, hemisphere: str, x: float, y: float) -> dict:
        """
        Convert UTM coordinates to latitude and longitude.
        Hemisphere should be 'N' or 'S'.
        """
        if hemisphere.upper() not in {"N", "S"}:
            raise ValueError("Hemisphere must be 'N' or 'S'")

        if hemisphere.upper() == "S":
            y -= 10_000_000

        proj = Proj(proj="utm", zone=zone, ellps="WGS84")
        lon, lat = proj(x, y, inverse=True)
        return {"longitude": lon, "latitude": lat}

    @staticmethod
    def translate2epsg(coord: tuple, epsg_src: int, epsg_dst: int) -> tuple:
        """
        Reproject coordinates from one EPSG system to another.
        """
        try:
            src = osr.SpatialReference()
            dst = osr.SpatialReference()
            src.ImportFromEPSG(epsg_src)
            dst.ImportFromEPSG(epsg_dst)

            trans = osr.CoordinateTransformation(src, dst)
            return trans.TransformPoint(coord[0], coord[1])
        except Exception as e:
            raise RuntimeError(f"Coordinate transformation failed: {e}")
