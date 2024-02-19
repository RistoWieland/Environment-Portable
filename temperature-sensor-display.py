# requirements:

import os
import glob
import time
import sys
import subprocess
sys.path.append('/home/kermit/bcm2835-1.71/1.44inch-LCD-HAT-Code/RaspberryPi/python')
import LCD_1in44
from PIL import Image,ImageDraw,ImageFont,ImageColor
import smbus
from datetime import datetime, timezone
import psycopg2
import socket
import configparser

# Config Register (R/W)
_REG_CONFIG                 = 0x00
# SHUNT VOLTAGE REGISTER (R)
_REG_SHUNTVOLTAGE           = 0x01

# BUS VOLTAGE REGISTER (R)
_REG_BUSVOLTAGE             = 0x02

# POWER REGISTER (R)
_REG_POWER                  = 0x03

# CURRENT REGISTER (R)
_REG_CURRENT                = 0x04

# CALIBRATION REGISTER (R/W)
_REG_CALIBRATION            = 0x05

class BusVoltageRange:
    """Constants for ``bus_voltage_range``"""
    RANGE_16V               = 0x00      # set bus voltage range to 16V
    RANGE_32V               = 0x01      # set bus voltage range to 32V (default)

class Gain:
    """Constants for ``gain``"""
    DIV_1_40MV              = 0x00      # shunt prog. gain set to  1, 40 mV range
    DIV_2_80MV              = 0x01      # shunt prog. gain set to /2, 80 mV range
    DIV_4_160MV             = 0x02      # shunt prog. gain set to /4, 160 mV range
    DIV_8_320MV             = 0x03      # shunt prog. gain set to /8, 320 mV range

class ADCResolution:
    """Constants for ``bus_adc_resolution`` or ``shunt_adc_resolution``"""
    ADCRES_9BIT_1S          = 0x00      #  9bit,   1 sample,     84us
    ADCRES_10BIT_1S         = 0x01      # 10bit,   1 sample,    148us
    ADCRES_11BIT_1S         = 0x02      # 11 bit,  1 sample,    276us
    ADCRES_12BIT_1S         = 0x03      # 12 bit,  1 sample,    532us
    ADCRES_12BIT_2S         = 0x09      # 12 bit,  2 samples,  1.06ms
    ADCRES_12BIT_4S         = 0x0A      # 12 bit,  4 samples,  2.13ms
    ADCRES_12BIT_8S         = 0x0B      # 12bit,   8 samples,  4.26ms
    ADCRES_12BIT_16S        = 0x0C      # 12bit,  16 samples,  8.51ms
    ADCRES_12BIT_32S        = 0x0D      # 12bit,  32 samples, 17.02ms
    ADCRES_12BIT_64S        = 0x0E      # 12bit,  64 samples, 34.05ms
    ADCRES_12BIT_128S       = 0x0F      # 12bit, 128 samples, 68.10ms

class Mode:
    """Constants for ``mode``"""
    POWERDOW                = 0x00      # power down
    SVOLT_TRIGGERED         = 0x01      # shunt voltage triggered
    BVOLT_TRIGGERED         = 0x02      # bus voltage triggered
    SANDBVOLT_TRIGGERED     = 0x03      # shunt and bus voltage triggered
    ADCOFF                  = 0x04      # ADC off
    SVOLT_CONTINUOUS        = 0x05      # shunt voltage continuous
    BVOLT_CONTINUOUS        = 0x06      # bus voltage continuous
    SANDBVOLT_CONTINUOUS    = 0x07      # shunt and bus voltage continuous


class INA219:
    def __init__(self, i2c_bus=1, addr=0x40):
        self.bus = smbus.SMBus(i2c_bus);
        self.addr = addr

        # Set chip to known config values to start
        self._cal_value = 0
        self._current_lsb = 0
        self._power_lsb = 0
        self.set_calibration_16V_5A()

    def read(self,address):
        data = self.bus.read_i2c_block_data(self.addr, address, 2)
        return ((data[0] * 256 ) + data[1])

    def write(self,address,data):
        temp = [0,0]
        temp[1] = data & 0xFF
        temp[0] =(data & 0xFF00) >> 8
        self.bus.write_i2c_block_data(self.addr,address,temp)

    def set_calibration_16V_5A(self):
        """Configures to INA219 to be able to measure up to 16V and 5A of current. Counter
           overflow occurs at 16A.
           ..note :: These calculations assume a 0.01 shunt ohm resistor is present
        """
        # By default we use a pretty huge range for the input voltage,
        # which probably isn't the most appropriate choice for system
        # that don't use a lot of power.  But all of the calculations
        # are shown below if you want to change the settings.  You will
        # also need to change any relevant register settings, such as
        # setting the VBUS_MAX to 16V instead of 32V, etc.

        # VBUS_MAX = 16V             (Assumes 16V, can also be set to 32V)
        # VSHUNT_MAX = 0.08          (Assumes Gain 2, 80mV, can also be 0.32, 0.16, 0.04)
        # RSHUNT = 0.01               (Resistor value in ohms)

        # 1. Determine max possible current
        # MaxPossible_I = VSHUNT_MAX / RSHUNT
        # MaxPossible_I = 8.0A

        # 2. Determine max expected current
        # MaxExpected_I = 5.0A

        # 3. Calculate possible range of LSBs (Min = 15-bit, Max = 12-bit)
        # MinimumLSB = MaxExpected_I/32767
        # MinimumLSB = 0.0001529              (61uA per bit)
        # MaximumLSB = MaxExpected_I/4096
        # MaximumLSB = 0,0012207              (488uA per bit)

        # 4. Choose an LSB between the min and max values
        #    (Preferrably a roundish number close to MinLSB)
        # CurrentLSB = 0.00016 (uA per bit)
        self._current_lsb = 0.1524  # Current LSB = 100uA per bit

        # 5. Compute the calibration register
        # Cal = trunc (0.04096 / (Current_LSB * RSHUNT))
        # Cal = 13434 (0x347a)

        self._cal_value = 26868

        # 6. Calculate the power LSB
        # PowerLSB = 20 * CurrentLSB
        # PowerLSB = 0.002 (2mW per bit)
        self._power_lsb = 0.003048  # Power LSB = 2mW per bit

        # 7. Compute the maximum current and shunt voltage values before overflow
        #
        # Max_Current = Current_LSB * 32767
        # Max_Current = 3.2767A before overflow
        #
        # If Max_Current > Max_Possible_I then
        #    Max_Current_Before_Overflow = MaxPossible_I
        # Else
        #    Max_Current_Before_Overflow = Max_Current
        # End If
        #
        # Max_ShuntVoltage = Max_Current_Before_Overflow * RSHUNT
        # Max_ShuntVoltage = 0.32V
        #
        # If Max_ShuntVoltage >= VSHUNT_MAX
        #    Max_ShuntVoltage_Before_Overflow = VSHUNT_MAX
        # Else
        #    Max_ShuntVoltage_Before_Overflow = Max_ShuntVoltage
        # End If

        # 8. Compute the Maximum Power
        # MaximumPower = Max_Current_Before_Overflow * VBUS_MAX
        # MaximumPower = 3.2 * 32V
        # MaximumPower = 102.4W

        # Set Calibration register to 'Cal' calculated above
        self.write(_REG_CALIBRATION,self._cal_value)

        # Set Config register to take into account the settings above
        self.bus_voltage_range = BusVoltageRange.RANGE_16V
        self.gain = Gain.DIV_2_80MV
        self.bus_adc_resolution = ADCResolution.ADCRES_12BIT_32S
        self.shunt_adc_resolution = ADCResolution.ADCRES_12BIT_32S
        self.mode = Mode.SANDBVOLT_CONTINUOUS
        self.config = self.bus_voltage_range << 13 | \
                      self.gain << 11 | \
                      self.bus_adc_resolution << 7 | \
                      self.shunt_adc_resolution << 3 | \
                      self.mode
        self.write(_REG_CONFIG,self.config)

    def getShuntVoltage_mV(self):
        self.write(_REG_CALIBRATION,self._cal_value)
        value = self.read(_REG_SHUNTVOLTAGE)
        if value > 32767:
            value -= 65535
        return value * 0.01

    def getBusVoltage_V(self):
        self.write(_REG_CALIBRATION,self._cal_value)
        self.read(_REG_BUSVOLTAGE)
        return (self.read(_REG_BUSVOLTAGE) >> 3) * 0.004

    def getCurrent_mA(self):
        value = self.read(_REG_CURRENT)
        if value > 32767:
            value -= 65535
        return value * self._current_lsb

    def getPower_W(self):
        self.write(_REG_CALIBRATION,self._cal_value)
        value = self.read(_REG_POWER)
        if value > 32767:
            value -= 65535
        return value * self._power_lsb


def open_connection(db): 
    global connection
    config = configparser.ConfigParser()
    config.read('/home/kermit/Config/config.ini')
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


def create_table(db):
    open_connection(db)
    
    try:
        create_table_query = '''CREATE TABLE pfannenstiel(
               timeStamp TIMESTAMP,
               temperature REAL
            ); '''       
        
        cursor.execute(create_table_query)
        connection.commit()
        close_connection()
        
    except Exception as err:
        print ("Table pfannenstiel already exists")
        close_connection()

    else:
        print("Table pfannenstiel created successfully in PostgreSQL")
        close_connection()


def drop_table():
    open_connection()
    
    try:
        cursor.execute("Drop table pfannenstiel;")
        connection.commit()
        close_connection()
        
    except (Exception, psycopg2.Error) as error:
        print ("Table pfannenstiel does not exists")
        print ("Error while connecting to PostgreSQL", error)
        close_connection()

    else:
        print("Table pfannenstiel dropped successfully in PostgreSQL ")
        close_connection()


def insert_records(db, temperature):
    open_connection(db)
    try:
        dt = datetime.now()
        x = dt.replace(microsecond=0)  
        postgres_insert_query = """ INSERT INTO pfannenstiel (timeStamp, temperature) VALUES (%s,%s)"""
        record_to_insert = (x, temperature)
        cursor.execute(postgres_insert_query, record_to_insert)
        connection.commit()
        close_connection()

    except (Exception, psycopg2.Error) as error:
        print ("Error while connecting to PostgreSQL", error)
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
 
base_dir = '/sys/bus/w1/devices/'
device_folder = glob.glob(base_dir + '28*')[0]
device_file = device_folder + '/w1_slave'
 
def read_temp_raw():
    f = open(device_file, 'r')
    lines = f.readlines()
    f.close()
    return lines
 
def read_temp():
    lines = read_temp_raw()
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp_raw()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = round(float(temp_string) / 1000.0, 1)
        return temp_c

# Define menu items and structure
main_menu = {
    "Settings": {
        "Record Interval": {
            "30sec",
            "1min",
            "2min",
            "5min",
            "10min",
            "15min",
            "30min",
            "60min"
        },
        "Display Sleep": {
            "Never",
            "1min",
            "2min",
            "5min",
            "10min",
            "15min",
            "30min",
            "60min"
        },
        "Recording Delay": {
            "No",
            "1min",
            "2min",
            "5min",
            "10min",
            "15min",
            "30min",
            "60min"
        }
    }
}


def menu():
    menu_items = list(main_menu.keys())
    num_items = len(menu_items)
    selected_index = 0  # Start with the first item selected

    while True:
        # Clear screen
        image = Image.new("RGB", (LCD.width, LCD.height), "BLACK")
        draw = ImageDraw.Draw(image)

        # Determine the range of items to display (5 items in the middle)
        start_index = max(0, selected_index - 2)
        end_index = min(num_items, selected_index + 3)

        # Display menu items
        for i, index in enumerate(range(start_index, end_index)):
            item_name = menu_items[index]
            fill_color = "WHITE" if i == 2 else "GRAY"  # Highlight selected item
            draw.text((5, 10 + i * 30), item_name, font=font_1, fill=fill_color)

        # Display the selection rectangle
        selection_rect_y = 10 + (selected_index - start_index) * 30
        draw.rectangle([(0, selection_rect_y), (LCD.width, selection_rect_y + 30)], outline="YELLOW")

        # Show the image on the LCD
        LCD.LCD_ShowImage(image, 0, 0)

        # Check button input
        if LCD.digital_read(LCD.GPIO_KEY_UP_PIN) == 1:  # Button up is pressed
            selected_index = (selected_index - 1) % num_items
        elif LCD.digital_read(LCD.GPIO_KEY_DOWN_PIN) == 1:  # Button down is pressed
            selected_index = (selected_index + 1) % num_items
        elif LCD.digital_read(LCD.GPIO_KEY_LEFT_PIN) == 1:  # Button left is pressed
            return  # Go one level higher
        elif LCD.digital_read(LCD.GPIO_KEY_RIGHT_PIN) == 1:  # Button right is pressed
            selected_item = menu_items[selected_index]
            submenu = main_menu[selected_item]
            if isinstance(submenu, dict):  # If submenu exists, go one level deeper
                setting_menu(submenu)
            elif submenu == "Back":  # If it's a "Back" option, go one level higher
                return
        elif LCD.digital_read(LCD.GPIO_KEY_PRESS_PIN) == 1:  # Button center is pressed
            selected_item = menu_items[selected_index]
            action = main_menu[selected_item]
            if isinstance(action, dict):  # If it's a submenu, go one level deeper
                setting_menu(action)
            elif callable(action):  # If it's a function, execute it
                action()

        time.sleep(0.2)  # Debounce button press


LCD = LCD_1in44.LCD()
Lcd_ScanDir = LCD_1in44.SCAN_DIR_DFT  #SCAN_DIR_DFT = D2U_L2R
LCD.LCD_Init(Lcd_ScanDir)
LCD.LCD_Clear()

# Load a font
font_path = "/home/kermit/Environment-Portable/JMH Typewriter-Bold.ttf"
font_size_1 = 18
font_1 = ImageFont.truetype(font_path, font_size_1)
font_size_2 = 44
font_2 = ImageFont.truetype(font_path, font_size_2)
font_size_3 = 26
font_3 = ImageFont.truetype(font_path, font_size_3)

# Create an INA219 instance.
ina219 = INA219(addr=0x43)

# drop_table()
# create_table("remote")
# create_table("local")

# to control if temperature meassurement results should be write in the db or no
# after boot the results should not be written by default
recording = False

# set recording to db interval in seconds
recording_interval = 60 
# Initialize variables for timestamp and flag
recording_last_upload_time = time.time() - recording_interval # Get current timestamp minus interval to start recording immediately
recording_time_elapsed = False

# used to not toggle between start recording and stop recording too fast
toggle = 3

db_location = ""

while True:
    # clear screen
    image = Image.new("RGB", (LCD.width, LCD.height), "BLACK")
    draw = ImageDraw.Draw(image)
    
    # UPS Hat readings
    bus_voltage = ina219.getBusVoltage_V()             # voltage on V- (load side)
    shunt_voltage = ina219.getShuntVoltage_mV() / 1000 # voltage between V+ and V- across the shunt
    current = ina219.getCurrent_mA()                   # current in mA
    power = ina219.getPower_W()                        # power in W
    p = (bus_voltage - 3)/1.2*100
    if(p > 100):p = 100
    if(p < 0):p = 0
    battery = str(round(p,1))

    # temperature reading
    temperature = read_temp()
    temperature_str = str(temperature)

    # check if recording. If so then change the color to green. If no recording then change color to red
    if recording:
        font_color = "GREEN"
    if not recording:
        font_color = "RED"
        db_location = ""

    # display result to display
    draw.text((5, 0), 'Temperatur: ', font=font_1, fill = "WHITE")
    draw.text((5, 30), temperature_str+'°C ', font=font_2, fill = font_color)
    draw.text((5, 82), 'DB : '+db_location, font=font_1, fill = "WHITE")
    draw.text((5, 105), 'Bat: '+battery+'%', font=font_1, fill = "WHITE")
    LCD.LCD_ShowImage(image,0,0)

    # Check if one minute has passed
    if time.time() - recording_last_upload_time >= recording_interval:
        recording_time_elapsed = True
        recording_last_upload_time = time.time()  # Update timestamp

    # check if network connection then write results remote and synch database local to remote. 
    # if no network connection then write result local
    if check_network_connection() and recording and recording_time_elapsed:
        insert_records("remote", temperature)
        move_records_to_remote_db()
        recording_time_elapsed = False
        db_location = "remote"
    if not check_network_connection() and recording and recording_time_elapsed:
        insert_records("local", temperature)
        recording_time_elapsed = False
        db_location = "local"

    # check if Key3 is pressed or battery power is smaller than 5%. If so then shutdown system
    if LCD.digital_read(LCD.GPIO_KEY3_PIN) == 1 or p < 5: 
       print ("System Shutdown")
       image = Image.new("RGB", (LCD.width, LCD.height), "BLACK")
       draw = ImageDraw.Draw(image)
       draw.text((5, 0), 'System', font=font_3, fill = "YELLOW")
       draw.text((5, 40), 'Shutdown', font=font_3, fill = "YELLOW")
       LCD.LCD_ShowImage(image,0,0)
       time.sleep(5)
       subprocess.run(["sudo", "shutdown", "-h", "now"])

    # check if Key2 is pressed. If so then stop recording
    if LCD.digital_read(LCD.GPIO_KEY2_PIN) == 1:
        print ("Delete all records locally and remotely")
        image = Image.new("RGB", (LCD.width, LCD.height), "BLACK")
        draw = ImageDraw.Draw(image)
        draw.text((5, 10), 'Delete', font=font_3, fill = "YELLOW")
        draw.text((5, 50), 'All', font=font_3, fill = "YELLOW")
        draw.text((5, 90), 'Records', font=font_3, fill = "YELLOW")
        LCD.LCD_ShowImage(image,0,0)
        time.sleep(3)
        delete_all_records("local")
        delete_all_records("remote")

    # check if Key1 is pressed then toggle between recording and not recording
    if LCD.digital_read(LCD.GPIO_KEY1_PIN) == 1 and toggle > 2:
        recording = not recording
        toggle -= 1
    if LCD.digital_read(LCD.GPIO_KEY1_PIN) == 0:
        toggle = 3

    # check if center button of joystick is pressed
    if LCD.digital_read(LCD.GPIO_KEY_PRESS_PIN) == 1: # button is released
        menu()




