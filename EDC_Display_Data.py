
import ast
import psycopg2
import sys
import os
import configparser
import time
import datetime
import spidev

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


def close_connection():
    cursor.close()
    connection.close()


def move_records_to_remote_db(table_name):
    open_connection("local")
    try:
        # I limit the fetching to 10 entries everytime we need to move in order to still let the every minute interval be able to perform
        select_query = f'''
        SELECT * FROM {table_name}
        LIMIT 10; 
        '''
        cursor.execute(select_query)
        records = cursor.fetchall()
        close_connection()
    except (Exception, psycopg2.Error) as error:
        print("Error while moving records to remote PostgreSQL", error)
        close_connection()

    open_connection("remote")
    try:
        for record in records:
            insert_query = f'''
            INSERT INTO {table_name} (timestamp, t0, t1, t2, t3, humidity) VALUES (%s,%s,%s,%s,%s,%s);
            '''
            cursor.execute(insert_query, record)    
        connection.commit()
        close_connection()
    except (Exception, psycopg2.Error) as error:
        print("Error while moving records to remote PostgreSQL", error)
        close_connection()

    open_connection("local")
    try:
        delete_query = f'''
        DELETE FROM {table_name};
        '''
        cursor.execute(delete_query)
        connection.commit()
        close_connection()
    except (Exception, psycopg2.Error) as error:
        print("Error while moving records to remote PostgreSQL", error)
        close_connection()



global font, disp, image
# 128x32 display with hardware SPI:
disp = SSD1305.SSD1305()
# Load Font
font = ImageFont.truetype('/home/statler/Environment-Portable/JMH Typewriter-Bold.ttf',10)
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


def display_writing(values):
    # Draw a black filled box to clear the image.
    draw.rectangle((0,0,width,height), outline=0, fill=0)
    draw.text((0, 0), "TS : " + str(values[0]), font=font, fill=255)
    draw.text((0, 11), "t0 : " + str(values[1]) + "°C", font=font, fill=255)
    draw.text((0, 22), "t1 : " + str(values[2]) + "°C", font=font, fill=255)
    draw.text((20, 11), "t2: " + str(values[3]) + "°C", font=font, fill=255)
    draw.text((20, 22), "t3 : " + str(values[4]) + "°C", font=font, fill=255)
    disp.getbuffer(image)
    disp.ShowImage()