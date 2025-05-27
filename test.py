import os
from crontab import CronTab
import datetime
import subprocess
import sys
from datetime import datetime
import numpy as np
from PIL import Image
from sqlmodel import select
import csv
from pyproj import Proj
from osgeo import ogr, osr, gdal

from database.main import Database
from models.XmprData import XmprData


gdal.DontUseExceptions()

CS = CoordinateSystem()
MG = ModGdal()
DB = Database()



class TranslateFormat:
    def __init__(self):
        pass

    @staticmethod
    def main(csv_path, ssv_path):
        print(csv_path)
        # output_space_delimited_file = file_name + ".txt"
        with open(csv_path, mode='r') as csv_file, open(ssv_path, mode='w') as space_file:
            csv_reader = csv.reader(csv_file)
            for row in csv_reader:
                space_delimited_line = ' '.join(row)
                space_file.write(space_delimited_line + '\n')

class ModGdal:
    def __init__(self):
        pass

    @staticmethod
    def ascii2tiff(epsg, ascii_name, tiff_name) -> int:
        print(f"make_tiff {epsg} {tiff_name}")
        try:
            opt = gdal.TranslateOptions(
                format="GTiff",
                outputSRS=f"EPSG:{epsg}",
            )
            gdal.Translate(tiff_name, ascii_name, options=opt)
        except Exception as e:
            print(e)
        return 1

class CoordinateSystem:
    def __init__(self):
        pass

    @staticmethod
    def latlon2utm(lon, lat):
        e2u_zone = int(divmod(lon, 6)[0]) + 31

        e2u_conv = Proj(proj='utm', zone=e2u_zone, ellps='WGS84')
        utm_x, utm_y = e2u_conv(lon, lat)
        if lat < 0:
            utm_y = utm_y + 10000000

        epsg = 32600 + e2u_zone
        print(f"UTM zone is {e2u_zone} \n"
              f"UTM epsg is {epsg} \n"
              f"UTM East is {utm_x},[m] \n"
              f"UTM North is {utm_y}, [m]")

        return {
            "zone": e2u_zone,
            "epsg": epsg,
            "x": utm_x,
            "y": utm_y
        }

    # UTM to LatLon
    # hemisphere = 'N' or 'S'
    @staticmethod
    def utm2latlon(zone, hemisphere, utm_x, utm_y):
        # Add offset if the point in the southern hemisphere
        if hemisphere == 'S':
            utm_y = utm_y - 10000000

        # Define coordinate converter
        e2u_conv = Proj(proj='utm', zone=zone, ellps='WGS84')
        # Convert UTM2EQA
        lon, lat = e2u_conv(utm_x, utm_y, inverse=True)

        print(f"Longitude is {lon}, [deg.] \n"
              f"Latitude is  {lat}, [deg.]")

        return {
            "longitude": lon,
            "latitude": lat
        }

    @staticmethod
    def translate2epsg(coordinate, epsg_src, epsg_dst):
        try:
            src_srs, dst_srs = osr.SpatialReference(), osr.SpatialReference()
            src_srs.ImportFromEPSG(epsg_src)
            dst_srs.ImportFromEPSG(epsg_dst)
            trans = osr.CoordinateTransformation(src_srs, dst_srs)
            return trans.TransformPoint(coordinate[0], coordinate[1])
        except Exception as e:
            print(e)
            return None

class CrontabControl:
    def __init__(self, logger):
        self.logger = logger
        self.cron = None

    def write_job(self, command):
        self.cron = CronTab(tab=command)

    def run_job(self):
        for result in self.cron.run_scheduler():
            print(result)
            if result.returncode == 0:
                self.logger.log(f"OK : {result.stdout}")
            else:
                self.logger.log(f"Err: {result.stderr}")


def main(csv_name):
    print(csv_name)
    if not os.path.exists(f"/images/tif"):
        os.makedirs(f"/images/tif")
    if not os.path.exists(f"/images/png"):
        os.makedirs(f"/images/png")
    lat = 2.155930
    lon = 102.732700
    basename = os.path.splitext(os.path.basename(csv_name))[0]
    polar_ssv = "/app/polar2mesh/temp.ssv"
    mesh_ssv = "/app/polar2mesh/test.ssv"
    utm = CS.latlon2utm(lon, lat)

    csv_dir = "/images/tif"
    b_name = os.path.basename(csv_name)
    parts = b_name.split("_")
    date_str = parts[0]
    year = date_str[:4]
    month = date_str[4:6]
    day = date_str[6:8]
    time_str = parts[1]
    hour = time_str[:2]
    minute = time_str[2:4]
    second = time_str[4:6]
    tif_dir = os.path.join("/images/tif", year, month, day)
    png_dir = os.path.join("/images/png", year, month, day)

    if not os.path.exists(tif_dir):
        os.makedirs(tif_dir)

    if not os.path.exists(png_dir):
        os.makedirs(png_dir)

    TranslateFormat.main(csv_name, polar_ssv)

    try:
        subprocess.run(f"/app/polar2mesh/polar2mesh {polar_ssv} {mesh_ssv}", shell=True)
    except Exception as e:
        print(e)
        return 0
    if not os.path.exists(mesh_ssv):
        file_delete(polar_ssv, mesh_ssv)
        return 0

    tif_path = os.path.join(tif_dir, f'{basename}.tif')
    MG.ascii2tiff(utm['epsg'], mesh_ssv, tif_path)
    data = np.loadtxt(mesh_ssv, delimiter=' ', skiprows=6)

    png_path = os.path.join(png_dir, f'{basename}.png')
    ascii2img(data, png_path)

    db = DB.get_session()
    res = db.exec(select(XmprData).where(XmprData.csv == csv_name)).first()
    if res:
        print("Already exists")
        file_delete(polar_ssv, mesh_ssv)
        return 0

    db.add(XmprData(
        id=1,
        time=datetime.strptime(f'{year}-{month}-{day} {hour}:{minute}:{second}', '%Y-%m-%d %H:%M:%S'),
        csv=csv_name,
        image=png_path,
        geotiff=tif_path
    ))
    db.commit()
    db.close()
    file_delete(polar_ssv, mesh_ssv)
    return 1


def ascii2img(data, png_path):
    num_rows, num_cols = data.shape
    print(num_rows, num_cols)
    image = Image.new("RGBA", (num_cols, num_rows), (0, 0, 0, 0))
    pixels = image.load()
    for y in range(int(num_rows)):
        for x in range(int(num_cols)):
            ascii_value = data[y, x]
            if float(ascii_value) <= 0:
                pixels[x, y] = (0, 0, 0, 0)
                continue
            alpha = 255 - ascii_value
            red, green, blue = get_color(ascii_value)
            pixels[x, y] = (red, green, blue, 200)

    image.save(png_path, 'PNG')


def get_color(v):
    if 0 < v < 1:
        return 243, 243, 254
    elif 1 <= v < 5:
        return 171, 213, 255
    elif 5 <= v < 10:
        return 75, 151, 255
    elif 10 <= v < 20:
        return 66, 91, 255
    elif 20 <= v < 30:
        return 253, 249, 84
    elif 30 <= v < 50:
        return 245, 164, 78
    elif 50 <= v < 80:
        return 240, 77, 73
    else:
        return 183, 54, 127


def file_delete(polar_ssv, mesh_ssv):
    if os.path.exists(polar_ssv):
        os.remove(polar_ssv)
    if os.path.exists(mesh_ssv):
        os.remove(mesh_ssv)

def move_files():
    # Move raw files to the raw directory
    # ROOT_DIR = f'/mnt/RAID-01/OBS/X-bandMP/{OBS}'
    ROOT_DIR = '/data'
    SAVE_DIR = os.path.join(ROOT_DIR, 'csv')
    CSV_DIR = os.path.join(ROOT_DIR, 'converted')

    os.chdir(SAVE_DIR)

    for filename in os.listdir('.'):
        B_NAME = os.path.basename(filename)
        parts = B_NAME.split('_')
        date_str = parts[0]
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        TARGET_DIR = os.path.join(CSV_DIR, year, month, day)

        if not os.path.exists(TARGET_DIR):
            os.makedirs(TARGET_DIR)

        if parts[2] == 'Rain' and parts[3] == '000.csv':
            main(os.path.join(SAVE_DIR, filename))

        # Uncomment the following line if you want to move the files to TARGET_DIR
        # os.rename(filename, os.path.join(TARGET_DIR, filename))
        os.rename(filename, os.path.join(TARGET_DIR, filename))

    print("Done.")


def move_row_files():
    # Move raw files to the raw directory
    # ROOT_DIR = f'/mnt/RAID-01/OBS/X-bandMP/{OBS}'
    ROOT_DIR = '/data'
    SAVE_DIR = os.path.join(ROOT_DIR, 'rain-RT')
    RAW_DIR = os.path.join(ROOT_DIR, 'raw')

    os.chdir(SAVE_DIR)

    for filename in os.listdir('.'):
        parts = filename.split('_')
        date_str = parts[1]
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        TARGET_DIR = os.path.join(RAW_DIR, year, month, day)

        if not os.path.exists(TARGET_DIR):
            os.makedirs(TARGET_DIR)

        os.rename(filename, os.path.join(TARGET_DIR, filename))

    print("Done.")


def file_move():

    move_row_files()
    move_files()
    

logs_dir = "/app/logs"

if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

logger = Logger(logs_dir)

cc = CrontabControl(logger)

# 10分間隔で実行
command = f"*/5 * * * * {file_move()}"
cc.write_job(command)
cc.run_job()
