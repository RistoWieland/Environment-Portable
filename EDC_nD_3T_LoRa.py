# requirements:
# sudo apt install python3-psycopg2
#
# Need to disable the serial login shell and have to enable serial interface 
# command `sudo raspi-config`
# When the LoRaHAT is attached to RPi, the M0 and M1 jumpers of HAT should be removed.

import os
import glob
import time
import psycopg2
import socket
import configparser
from datetime import datetime, timezone
import sys
import threading
import select
import termios
import tty
import glob
from threading import Timer
# sys.path.append('/home/kermit/SX126X_LoRa_HAT_Code/raspberrypi/python')
import sx126x


def settings_reading(which_section, which_parameter):
    config = configparser.ConfigParser()
    config.read(config_file)
    reading = config[which_section][which_parameter]
    return reading


# where the config file is located and load it as global variable
global config_file
config_file = '/home/statler/Config/config.ini'


# here I keep track of which version this script is
script_version = "v1.01"
release_notes ="changed the config file config.ini and added release notes"


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


def insert_records(db, temperatures):
    open_connection(db)

    try:
        # Round timestamp to zero seconds
        dt = datetime.now().replace(second=0, microsecond=0)

        # Prepare the insert query dynamically for each temperature column
        temperature_columns = ', '.join(f't{i}' for i in range(len(temperatures)))
        temperature_placeholders = ', '.join('%s' for _ in range(len(temperatures)))

        postgres_insert_query = f"""
            INSERT INTO waermepumpe (timeStamp, {temperature_columns})
            VALUES (%s, {temperature_placeholders})
        """
        print(postgres_insert_query)
        # Record to insert including rounded timestamp and temperatures
        record_to_insert = [dt, *temperatures]
        print(record_to_insert)

        cursor.execute(postgres_insert_query, record_to_insert)
        connection.commit()
        print("Data inserted successfully!")
        close_connection()

    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL:", error)
        close_connection()


def check_network_connection():
    try:
        # Try to connect to a well-known external server
        socket.create_connection(("8.8.8.8", 53), timeout=0.5)
        return True
    except OSError:
        return False


def delete_all_records(db):
    open_connection(db)
    try:
        cursor.execute("DELETE FROM pfannenstiel;")
        connection.commit()
        close_connection()
    except (Exception, psycopg2.Error) as error:
        print("Error while moving records to remote PostgreSQL", error)
        close_connection()


def move_records_to_remote_db():
    open_connection("local")
    try:
        cursor.execute("SELECT * FROM pfannenstiel;")
        records = cursor.fetchall()
        close_connection()
    except (Exception, psycopg2.Error) as error:
        print("Error while fetching records from local PostgreSQL", error)
        close_connection()
        return  # Exit the function if an error occurs or no records are found

    # If there are no records, skip the rest of the function
    if not records:
        print("No records found in local database. Skipping the rest of the function.")
        return

    open_connection("remote")
    try:
        for record in records:
            print(record)
            postgres_insert_query = """ INSERT INTO pfannenstiel (timeStamp, temperature) VALUES (%s,%s)"""
            cursor.execute(postgres_insert_query, record)    
        connection.commit()
        close_connection()
        delete_all_records("local")  # This line should be inside the try block
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


def send_lora_data(index):
    data = bytes([255]) + bytes([255]) + bytes([18]) + bytes([255]) + bytes([255]) + bytes([12]) + "t"+str(index)+":".encode()+str(read_temp(index)).encode()+" C".encode()
    print(data)
    node.send(data)
    time.sleep(10)


drop_table("local", settings_reading("local","table"))
create_table("local", settings_reading("local","table"))

while True:
    temp = []  # Initialize an empty list
    for i in range(number_of_sensors):
        value = read_temp(i)
        temp.append(value)
        send_lora_data(i)
    insert_records("local", temp)
    time.sleep(60)
