# requirements:
# sudo apt install python3-psycopg2
# sudo apt install python3-serial
#
# Need to disable the serial login shell and have to enable serial interface 
# command `sudo raspi-config`
# When the LoRaHAT is attached to RPi, the M0 and M1 jumpers of HAT should be removed.

import ast
import psycopg2
import sys
import threading
import time
import select
import tty
from threading import Timer
sys.path.append('/home/statler/SX126X_LoRa_HAT_Code')
import sx126x



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
    db_params = {
        "db1": {
            "user": "postgres",
            "password": "Qyyx7Gu39Fpo.y6!inE3wLVa9LoujK",
            "host": "172-232-207-139.ip.linodeusercontent.com",
            "port": "5432",
            "database": "jupiterstrasse_env",
            "sslmode": "verify-full"
        }
    }

    if db in db_params:
        params = db_params[db]
        try:
            global connection
            connection = psycopg2.connect(
                user=params["user"],
                password=params["password"],
                host=params["host"],
                port=params["port"],
                database=params["database"],
                # options=f'-c password_encryption=scram-sha-256',
                sslmode=params["sslmode"]
            )
            global cursor
            cursor = connection.cursor()
            print(f"Connection to {db} database successful")
            return
        except (Exception, psycopg2.Error) as error:
            print(f"Error while connecting to {db} database:", error)
            return
    else:
        print(f"Database {db} not found in parameters")
        return 


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



try:
    while True:
        received_message = node.receive()
        if received_message is not None:
            print("Received message:", received_message)
            print(type(received_message))
            # Remove the leading 'b' character
            if received_message.startswith('b'):
                received_message = received_message[1:]
            # Clean up the string further
            received_message = received_message.strip("'")  # Remove surrounding single quotes
            temperatures = ast.literal_eval(received_message)
            print(temperatures)
            print(type(temperatures))
            insert_records("db1", temperatures)
except Exception as e:
    print("Error:", e)



