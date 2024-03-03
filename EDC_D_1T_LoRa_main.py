# requirements:
# sudo apt install python3-psycopg2
# sudo apt install python3-serial
# sudo pip3 install RPi.bme280
# sudo apt update
# sudo apt install python3-pip
# sudo apt install python3-pil
# sudo apt install python3-numpy
# sudo pip3 install spidev
#
# Need to disable the serial login shell and have to enable serial interface 
# Enable I2C
# Enable SPI
# command `sudo raspi-config`
# When the LoRaHAT is attached to RPi, the M0 and M1 jumpers of HAT should be removed.

import ast
import psycopg2
import sys
import threading
import configparser
import socket
import time
import datetime
import select
import tty
import smbus2
import bme280
from PIL import Image,ImageDraw,ImageFont,ImageColor
from threading import Timer
sys.path.append('/home/statler/SX126X_LoRa_HAT_Code')
import sx126x
sys.path.append('/home/statler/1.44inch-LCD-HAT-Code')
import LCD_1in44


# where the config file is located and load it as global variable
global config_file
config_file = '/home/statler/Config/config.ini'

# here I keep track of which version this script is
script_version = "v1.00"
release_notes ="initial version"


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


# write this version number of this script into the config file
settings_writing("info", "version", script_version)
# write release notes into the config file
settings_writing("info", "release notes", release_notes)


# initialzing bme280 temperature, preassure, humidity sensor
port = 1
address = 0x76 # Adafruit BME280 address. Other BME280s may be different. check with: sudo i2cdetect -y 1
bus = smbus2.SMBus(port)
bme280.load_calibration_params(bus,address)


#   serial_num
#       PiZero, Pi3B+, and Pi4B use "/dev/ttyS0"
#
#    Frequency is [850 to 930], or [410 to 493] MHz
#
#    address is 0 to 65535
#        under the same frequence,if set 65535,the node can receive 
#        messages from another node of address is 0 to 65534 and similarly,
#        the address 0 to 65534 of node can receive messages while 
#        the another note of address is 65535 sends.
#        otherwise two node must be same the address and frequence
#
#    The tramsmit power is {10, 13, 17, and 22} dBm
#
#    RSSI (receive signal strength indicator) is {True or False}
#        It will print the RSSI value when it receives each message
#
node = sx126x.sx126x(serial_num = "/dev/ttyS0",freq=868,addr=0,power=22,rssi=True,air_speed=2400,relay=False)

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


def create_table(db, table_name):
    open_connection(db)
    
    try:
        create_table_query = f'''
            CREATE TABLE {table_name} (
                timeStamp TIMESTAMP,
                t0 REAL,
                t1 REAL,
                t2 REAL,
                t3 REAL,
                humidity REAL
            );
        '''
        
        cursor.execute(create_table_query)
        connection.commit()
        close_connection()
        
    except Exception as err:
        print ("Table", table_name, "already exists")
        close_connection()

    else:
        print("Table", table_name, "created successfully in PostgreSQL")
        close_connection()


def drop_table(db, table_name):
    open_connection(db)

    try:
        drop_table_query = f'''
            DROP TABLE {table_name};
            '''
        cursor.execute(drop_table_query)
        connection.commit()
        close_connection()
        
    except (Exception, psycopg2.Error) as error:
        print ("Table", table_name, "does not exists")
        print ("Error while connecting to PostgreSQL", error)
        close_connection()

    else:
        print("Table", table_name, "dropped successfully in PostgreSQL")
        close_connection()


def insert_records(db, temperatures, table_name):
    open_connection(db)

    try:
        # reading the local environment sensor
        bme280_data = bme280.sample(bus, address)
        local_humidity = round(bme280_data.humidity)
        local_temperature = round(bme280_data.temperature, 1)
        
        # Extract timestamp from temperatures
        timestamp = temperatures[0]

        # Check if timestamp already exists in the database
        check_query = f"""
            SELECT COUNT(*) FROM {table_name} WHERE timeStamp = %s
        """
        cursor.execute(check_query, (timestamp,))
        result = cursor.fetchone()[0]
        if result > 0:
            print("Timestamp already exists, skipping insertion.")
            return  # Skip insertion if timestamp already exists

        # Prepare the insert query dynamically for each temperature column
        temperature_columns = ', '.join(f't{i}' for i in range(len(temperatures) - 1))
        temperature_columns += ', t3, humidity'

        # Prepare the placeholders for temperature values
        temperature_placeholders = ', '.join('%s' for _ in range(len(temperatures) - 1))
        temperature_placeholders += ', %s, %s'

        # Construct the values to be inserted (timestamp followed by temperature values)
        values = temperatures[1:] + [local_temperature, local_humidity]

        # Construct the query with placeholders
        insert_query = f"""
            INSERT INTO {table_name} (timeStamp, {temperature_columns})
            VALUES (%s, {temperature_placeholders})
        """

        # Record to insert including rounded timestamp and temperatures
        cursor.execute(insert_query, [timestamp] + values)
        connection.commit()
        print("Data inserted", db, "successfully!")
        close_connection()

    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL:", error)
        close_connection()


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


def check_network_connection():
    try:
        # Try to connect to a well-known external server
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except OSError:
        return False


def send_lora_data(temperatures):
    data = bytes([255]) + bytes([255]) + bytes([18]) + bytes([255]) + bytes([255]) + bytes([12]) + str(temperatures).encode()
    node.send(data)


def display_writing(temperatures):
    image = Image.new("RGB", (LCD.width, LCD.height), "BLACK")
    draw = ImageDraw.Draw(image)
    draw.text((5, 0), 'Temperatures: ', font=font_1, fill = "WHITE")
    draw.text((5, 18), 'Date/Time' + str(temperatures[0]), font=font_1, fill = "WHITE")
    draw.text((5, 36), 't0 : ' + str(temperatures[1]) + '°C', font=font_1, fill = "GREEN")
    draw.text((5, 54), 't1 : ' + str(temperatures[2]) + '°C', font=font_1, fill = "GREEN")
    draw.text((5, 72), 't2 : ' + str(temperatures[3]) + '°C', font=font_1, fill = "GREEN")
    draw.text((5, 90), 't3 : ' + str(temperatures[4]) + '°C', font=font_1, fill = "GREEN")
    draw.text((5, 108), 'humidity : ' + str(temperatures[5]) + '%', font=font_1, fill = "GREEN")
    LCD.LCD_ShowImage(image,0,0)


# initalizing LCD
LCD = LCD_1in44.LCD()
Lcd_ScanDir = LCD_1in44.SCAN_DIR_DFT  #SCAN_DIR_DFT = D2U_L2R
LCD.LCD_Init(Lcd_ScanDir)
LCD.LCD_Clear()

# Load a font
font_path = "/home/statler/Environment-Portable/JMH Typewriter-Bold.ttf"
font_size_1 = 16
font_1 = ImageFont.truetype(font_path, font_size_1)
font_size_2 = 44
font_2 = ImageFont.truetype(font_path, font_size_2)
font_size_3 = 26
font_3 = ImageFont.truetype(font_path, font_size_3)
font_size_4 = 12
font_4 = ImageFont.truetype(font_path, font_size_4)


# drop_table("remote", settings_reading("remote","table"))
# create_table("remote", settings_reading("remote","table"))
# drop_table("local", settings_reading("local","table"))
# create_table("local", settings_reading("local","table"))


while True:
    image = Image.new("RGB", (LCD.width, LCD.height), "BLACK")
    draw = ImageDraw.Draw(image)
    draw.text((5, 0), 'Temperatures: ', font=font_1, fill = "WHITE")
    LCD.LCD_ShowImage(image,0,0)
    received_message = node.receive()
    if received_message is not None:
        # Remove the leading 'b' character
        if received_message.startswith('b'):
            received_message = received_message[1:]
        # Remove surrounding single quotes
        received_message = received_message.strip("'")
        temperatures = eval(received_message)
        display_writing(temperatures)
        if check_network_connection():
            insert_records("remote", temperatures, settings_reading("remote","table"))
            move_records_to_remote_db(settings_reading("remote","table"))
        else:
            insert_records("local", temperatures, settings_reading("local","table"))
        send_lora_data(temperatures)




