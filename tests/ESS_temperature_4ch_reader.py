# *******************************************************************************
# File:         ESS_temperature4ch_reader.py
# Date:         2020-07-24
# Author:       Garry Knight - Garry Knight, LLC
#
# Description:  LSST Environmental Sensors System (ESS) 4-channel temperature
#               instrument publisher using FTDI virtual serial port (VCP).
#
#               Provides an ESS instrument communication class and separate
#               thread controlling instrument read.
#
# *******************************************************************************
import serial
import threading
import time

ESS_INSTR_NAME = 'ESS_temperature_4ch_reader'

ERR_VAL: float = 'NaN'

# Serial Temperature Sensor data ....
SENSOR_CHANNEL_COUNT: int = 4
PREAMBLE_SIZE: int = 4
VALUE_SIZE: int = 9
DELIM_SIZE: int = 1
SENSOR_DATA_SIZE: int = PREAMBLE_SIZE + VALUE_SIZE + DELIM_SIZE
TERMINATOR_SIZE: int = 2
LINE_SIZE: int = (SENSOR_CHANNEL_COUNT * SENSOR_DATA_SIZE) - DELIM_SIZE
PREAMBLE_1: str = 'C01='
PREAMBLE_2: str = 'C02='
PREAMBLE_3: str = 'C03='
PREAMBLE_4: str = 'C04='
PREAMBLE_5: str = 'C05='
PREAMBLE_6: str = 'C06='
PREAMBLE_7: str = 'C07='
PREAMBLE_8: str = 'C08='
DELIMITER: str  = ','
TERMINATOR: str = '\r\n'
TEMPCHALL: str  = ''


# ----------------------------------------------------
# Tests numeric value & returns output data.
# ----------------------------------------------------
def testVal(preamble, sensorStr):
    val = ERR_VAL
    if sensorStr[0:PREAMBLE_SIZE] == preamble:
        try:
            val = float(sensorStr[PREAMBLE_SIZE:SENSOR_DATA_SIZE - 1])
        except Exception as e:
            raise ValueError (ESS_INSTR_NAME, ':', e)
    return val

# ----------------------------------------------------
# ESS temperature Instrument class
# ----------------------------------------------------
class ESS_Temperature_4ch:

    def __init__(
            self,
            uart = None,
            baudrate = 19200,
            timeout = 1.0):

        self._uart = uart
        self._baudrate = baudrate
        self._timeout = timeout
        
        '''
        Instrument channel outputs
        '''
        self.temperature_c00: float = None
        self.temperature_c01: float = None
        self.temperature_c02: float = None
        self.temperature_c03: float = None

        self.serial_port = serial.Serial(self._uart)
        self.serial_port.close()
        self.serial_port.baud = self._baudrate
        self.serial_port.timeout = timeout
        self.serial_port.rtscts = 0
        self.serial_port.open()

    def serial_open(self):
        self.serial_port.baudrate = self._baudrate
        self.serial_port.timeout = self._timeout
        self.serial_port.rtscts = 0
        self.serial_port.write_timeout = 1.0
        try:
            if not self.serial_port.isOpen():
                self.serial_port.open()
                print (ESS_INSTR_NAME, self.serial_port.name, "is open")
            else:
                print (ESS_INSTR_NAME, self.serial_port.name, "is already open")
        except:
            print (ESS_INSTR_NAME, self.serial_port.name, "Failed to open")
            raise

    def serial_close(self):
        try:
            serial_port.close()
            print (ESS_INSTR_NAME, self.serial_port.name, "closed")
        except:
            print (ESS_INSTR_NAME, self.serial_port.name, "Failed to close")
            raise
    
    def readInstrument(self):
        print ("")
        print (ESS_INSTR_NAME, ': Waiting for data ....')
        # read the instrument serial line
        ser_line = self.serial_port.readline()
        line = ''
        try:
            line = ser_line.decode('utf-8')[:-2]
        except:
            print (ESS_INSTR_NAME, ': Received line failed decode to utf-8. Ignoring received line')
        else:
            if len(line) == LINE_SIZE:
                temps = line.split(',', SENSOR_CHANNEL_COUNT-1)
                self.temperature_c00 = float(temps[0][PREAMBLE_SIZE:])
                self.temperature_c01 = float(temps[1][PREAMBLE_SIZE:])
                self.temperature_c02 = float(temps[2][PREAMBLE_SIZE:])
                self.temperature_c03 = float(temps[3][PREAMBLE_SIZE:])
            else:
                #raise RuntimeError (ESS_INSTR_NAME, ':', 'Serial timeout or other error')
                print (ESS_INSTR_NAME, ': Serial timeout or received line length error : ', line)

    # Publish 
    def publish(self):
        print (ESS_INSTR_NAME, ':', 'Temperature Ch0 =', self.temperature_c00)
        print (ESS_INSTR_NAME, ':', 'Temperature Ch1 =', self.temperature_c01)
        print (ESS_INSTR_NAME, ':', 'Temperature Ch2 =', self.temperature_c02)
        print (ESS_INSTR_NAME, ':', 'Temperature Ch3 =', self.temperature_c03)

# ----------------------------------------------------
# Instrument thread class ....
# DO NOT EDIT
# ----------------------------------------------------
class instrumentThread (threading.Thread):

    def __init__(self, threadID, instr):
        self.ess_instrument = instr
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.counter = 0
        
    def run(self):        
        # Run the main communication loop forever ....
        while True:
            self.ess_instrument.readInstrument()
            self.ess_instrument.publish()
            time.sleep(0.5)
            self.counter = self.counter + 1
            print(ESS_INSTR_NAME, ':', 'Running thread:', self.threadID, 'Count:', self.counter)

# ----------------------------------------------------
