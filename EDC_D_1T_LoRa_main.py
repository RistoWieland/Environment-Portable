# requirements:
# sudo apt install python3-psycopg2
# sudo apt install python3-serial
#
# Need to disable the serial login shell and have to enable serial interface 
# command `sudo raspi-config`
# When the LoRaHAT is attached to RPi, the M0 and M1 jumpers of HAT should be removed.

import json
import psycopg2
import sys
import threading
import time
import select
import termios
import tty
from threading import Timer
sys.path.append('/home/statler/SX126X_LoRa_HAT_Code')
import sx126x

old_settings = termios.tcgetattr(sys.stdin)
tty.setcbreak(sys.stdin.fileno())


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


def send_deal():
    get_rec = ""
    print("")
    print("input a string such as \033[1;32m0,868,Hello World\033[0m,it will send `Hello World` to lora node device of address 0 with 868M ")
    print("please input and press Enter key:",end='',flush=True)

    while True:
        rec = sys.stdin.read(1)
        if rec != None:
            if rec == '\x0a': break
            get_rec += rec
            sys.stdout.write(rec)
            sys.stdout.flush()

    get_t = get_rec.split(",")

    offset_frequence = int(get_t[1])-(850 if int(get_t[1])>850 else 410)
    #
    # the sending message format
    #
    #         receiving node              receiving node                   receiving node           own high 8bit           own low 8bit                 own 
    #         high 8bit address           low 8bit address                    frequency                address                 address                  frequency             message payload
    data = bytes([int(get_t[0])>>8]) + bytes([int(get_t[0])&0xff]) + bytes([offset_frequence]) + bytes([node.addr>>8]) + bytes([node.addr&0xff]) + bytes([node.offset_freq]) + get_t[2].encode()

    node.send(data)
    print('\x1b[2A',end='\r')
    print(" "*200)
    print(" "*200)
    print(" "*200)
    print('\x1b[3A',end='\r')
    


try:
    while True:
        node.receive()
except:
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)







