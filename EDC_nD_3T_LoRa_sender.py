# requirements:
# sudo apt install python3-psycopg2
# sudo apt install python3-serial
#
# Need to disable the serial login shell and have to enable serial interface 
# command `sudo raspi-config`
# When the LoRaHAT is attached to RPi, the M0 and M1 jumpers of HAT should be removed.

import os
import ast
import glob
import time
import psycopg2
import socket
import configparser
import datetime
import sys
import threading
import select
import termios
import tty
import glob
from threading import Timer
sys.path.append('/home/statler/SX126X_LoRa_HAT_Code')
import sx126x


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


# loading from config file how many temperature sensors are attached 
number_of_sensors = int(settings_reading("settings", "number sensors"))

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


def send_lora_data(temperatures):
    data = bytes([255]) + bytes([255]) + bytes([18]) + bytes([255]) + bytes([255]) + bytes([12]) + str(temperatures).encode()
    node.send(data)


def check_lora_data_received(sent_list): 
    timer = 10
    while timer > 0:
        received_message = node.receive()
        if received_message is not None:
            # Remove the leading 'b' character
            if received_message.startswith('b'):
                received_message = received_message[1:]
            # Clean up the string further
            received_message = received_message.strip("'")  # Remove surrounding single quotes
            received_list = eval(received_message)
            if received_list == sent_list:
                print("checked both list and they are equal")
                return True
        timer -= 1
        time.sleep(1)
    return False   


def open_connection(db): 
    global connection
    config = configparser.ConfigParser()
    config.read(config_file)
    connection = psycopg2.connect(user = config[db]["user"],
                                  password = config[db]["password"],
                                  host = config[db]["host"],
                                  port = config[db]["port"],
                                  database = config[db]["database"])
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
                t2 REAL
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
        # Extract timestamp from temperatures
        timestamp = temperatures[0]

        # Prepare the insert query dynamically for each temperature column
        temperature_columns = ', '.join(f't{i}' for i in range(len(temperatures) - 1))

        # Prepare the placeholders for temperature values
        temperature_placeholders = ', '.join('%s' for _ in range(len(temperatures) - 1))

        # Construct the values to be inserted (timestamp followed by temperature values)
        values = temperatures[1:]

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
    except (Exception, psycopg2.Error) as error:
        print("Error while moving records to remote PostgreSQL", error)
        close_connection()

    try:
        for record in records:
            record_list = list(record)  # Convert tuple to list
            send_lora_data(record_list)
            if check_lora_data_received(record_list):
                # Delete the processed records using timestamp
                timestamp = record_list[0]  # Assuming timestamp is the first element in record_list
                delete_query = f'''
                DELETE FROM {table_name}
                WHERE timeStamp = %s;
                '''
                cursor.execute(delete_query, (timestamp,))
                connection.commit()
        close_connection()
    except (Exception, psycopg2.Error) as error:
        print("Error while moving records to remote PostgreSQL", error)
        close_connection()


os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')
 
def read_temp(index):
    base_dir = '/sys/bus/w1/devices/'
    device_folder = glob.glob(base_dir + '28*')[index]
    device_file = device_folder + '/w1_slave'
    f = open(device_file, 'r')
    lines = f.readlines()
    f.close()
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp_raw()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = round(float(temp_string) / 1000.0, 1)
        return temp_c


# drop_table("local", settings_reading("local","table"))
# create_table("local", settings_reading("local","table"))

prev_minute = None  # Initialize the variable to track the previous minute

while True:
    current_minute = time.localtime().tm_min  # Get the current minute
    if current_minute != prev_minute:
        # Update the previous minute
        prev_minute = current_minute 
        # Initialize an empty list
        temperatures = []
        dt = datetime.datetime.now().replace(second=0, microsecond=0) # Round timestamp to zero seconds
        temperatures.append(dt)
        for i in range(number_of_sensors):
            value = read_temp(i)
            temperatures.append(value)
        send_lora_data(temperatures)
        # if we don't get the same string back from lora within 30s then we assume there is no conenction and temp is writen locally 
        if check_lora_data_received(temperatures):
            move_records_to_remote_db(settings_reading("local","table"))
        else:    
            insert_records("local", temperatures, settings_reading("local","table"))
    time.sleep(1)