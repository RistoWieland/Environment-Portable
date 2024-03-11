import ast
import psycopg2
import sys
import os
import configparser
import time
import datetime
import spidev
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw

libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'drive')
if os.path.exists(libdir):
    sys.path.append(libdir)
from drive import SSD1305


# where the config file is located and load it as global variable
global config_file
config_file = '/home/statler/Config/config.ini'


def settings_reading(which_section, which_parameter):
    config = configparser.ConfigParser()
    config.read(config_file)
    reading = config[which_section][which_parameter]
    return reading


def settings_writing(which_section, which_parameter, value):
    # Read existing config or create a new one
    config = configparser.ConfigParser()
    config.read(config_file)

    # Set the corresponding setting value
    config[which_section][which_parameter] = value

    # Write the updated config to the file
    with open(config_file, 'w') as configfile:
        config.write(configfile)


def open_connection(db): 
    try:
        global connection
        config = configparser.ConfigParser()
        config.read(config_file)
        connection = psycopg2.connect(user = config[db]["user"],
                                    password = config[db]["password"],
                                    host = config[db]["host"],
                                    port = config[db]["port"],
                                    database = config[db]["database"],
                                    sslmode = config[db]["sslmode"])
        global cursor
        cursor = connection.cursor()
    except Exception as err:
        return False


def close_connection():
    cursor.close()
    connection.close()


def parse_table(db, table_name):
    open_connection(db)
    try:
        # I limit the fetching to 1
        select_query = f'''
        SELECT * FROM {table_name} ORDER BY timestamp DESC LIMIT 1; 
        '''
        cursor.execute(select_query)
        record = cursor.fetchone()
        close_connection()
        return record
    except (Exception, psycopg2.Error) as error:
        print("Error while moving records to remote PostgreSQL", error)
        close_connection()


def display_writing(data_list):
    draw.rectangle((0,0,width,height), outline=0, fill=0)
    draw.text((0, 0), "TS: " + str(data_list[0]), font=font, fill=255)
    draw.text((0, 11), "T0: " + str(data_list[1]) + "°C", font=font, fill=255)
    draw.text((0, 22), "T1: " + str(data_list[2]) + "°C", font=font, fill=255)
    draw.text((64, 11), "T2: " + str(data_list[3]) + "°C", font=font, fill=255)
    draw.text((44, 22), "T3: " + str(data_list[4]) + "°C", font=font, fill=255)
    draw.text((88, 22), "T4: " + str(data_list[6]) + "°C", font=font, fill=255)
    disp.getbuffer(image)
    disp.ShowImage()


global font, disp, image
# 128x32 display with hardware SPI:
disp = SSD1305.SSD1305()
# Load Font
font = ImageFont.truetype('/home/statler/Environment-Portable/Fonts/Timeless.ttf',10)
# font = ImageFont.load_default()
# Initialize library.
disp.Init()
# Clear display.
disp.clear()
# Create blank image for drawing.
# Make sure to create image with mode '1' for 1-bit color.
width = disp.width
height = disp.height
image = Image.new('1', (width, height))
# Get drawing object to draw on image
draw = ImageDraw.Draw(image)


while True:
    record = parse_table("remote", settings_reading("remote","table"))
    display_writing(record)
    time.sleep(60)