from osgeo import gdal
import os

gdal.UseExceptions()

class ModGdal:
    @staticmethod
    def ascii2tiff(epsg: int, ascii_path: str, tiff_path: str) -> None:
        """
        Converts an ASCII raster (.ssv) to GeoTIFF using GDAL.

        Parameters:
            epsg (int): EPSG code for the spatial reference system.
            ascii_path (str): Path to the ASCII input file.
            tiff_path (str): Path to the GeoTIFF output file.
        """
        if not os.path.exists(ascii_path):
            raise FileNotFoundError(f"Input file not found: {ascii_path}")

        try:
            opts = gdal.TranslateOptions(
                format="GTiff",
                outputSRS=f"EPSG:{epsg}"
            )
            gdal.Translate(tiff_path, ascii_path, options=opts)

        except RuntimeError as e:
            raise RuntimeError(f"GDAL translation failed: {e}")

        if not os.path.exists(tiff_path):
            raise RuntimeError(f"GeoTIFF not created: {tiff_path}")
