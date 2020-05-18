# ****************************************************************************
# File:         ESS_Temperature4Ch_Publisher.py
# Date:         2020-05-11
# Author:       Garry Knight - Garry Knight, LLC
#
# Description:  LSST Environmental Sensors System (EAS) 4-channel temperature
#               instrument publisher using Service Abstraction Layer (SAL).
#               Written for Rapsberry Pi 4.
#
#               Provides an EAS instrument communication class
#               controlling instrument read and publish to SAL.
#
# ****************************************************************************

import time

from SALPY_ESS import *
import serialhat

# Edit this name to SAL entry for this instrument ....
ESS_INSTR_NAME = 'ESS_Temperature4Ch_Publisher'

ERR_VAL = -1999.999

# Serial Temperature instrument data stream ....
SENSOR_CHANNEL_COUNT = 4
PREAMBLE_SIZE = 4
VALUE_SIZE = 9
DELIM_SIZE = 1
SENSOR_DATA_SIZE = PREAMBLE_SIZE + VALUE_SIZE + DELIM_SIZE
TERMINATOR_SIZE = 2 
LINE_SIZE = TERMINATOR_SIZE + (SENSOR_CHANNEL_COUNT * (SENSOR_DATA_SIZE)) - 1
PREAMBLE_1 = 'C01='
PREAMBLE_2 = 'C02='
PREAMBLE_3 = 'C03='
PREAMBLE_4 = 'C04='
DELIMITER = ','
TERMINATOR = '\r\n'
TEMPCHALL = ''

# ----------------------------------------------------
# Tests numeric value & returns output data.
# ----------------------------------------------------
def testVal(preamble, sensorStr):
    val = ERR_VAL
    if sensorStr[0:PREAMBLE_SIZE] == preamble:
        try:
            val = float(sensorStr[PREAMBLE_SIZE:SENSOR_DATA_SIZE - 1])
        except:
            print (ESS_INSTR_NAME, ': Received data not valid')
    return val

# ----------------------------------------------------
# EAS Instrument Publisher class
#
# EDIT ONLY WHERE NOTED ****
# ----------------------------------------------------
class ESSInstrumentPublisher:

    def __init__(self, salid, uart, baudrate, timeout):
        
        self.name = ESS_INSTR_NAME
        self.uart = uart

        # SAL ....
        self.mgr = SAL_ESS(salid)
        # EDIT FOR INSTRUMENT HERE ****
        self.mgr.salTelemetryPub('ESS_Temperature4Ch')
        self.myData = ESS_Temperature4ChC()
                    
        # uart ....
        if uart == serialhat.UART1:
            self.serial_port = serialhat.serialhatrs422(self.uart)
            self.serial_port.close()
            self.serial_port.setReceive()
            self.serial_port.open(baudrate, timeout, False)
            self.serial_port.powerOn()
        else:
            self.serial_port = serialhat.serialhatrs232(self.uart)
            self.serial_port.close()
            self.serial_port.open(baudrate, timeout, False)
            self.serial_port.powerOn()

    def readInstrument(self):
        print ("")
        print (ESS_INSTR_NAME, ': Waiting for data ....')
        # read the instrument
        ser_line = self.serial_port.readLine()
        # Test and Populate SAL mData ....
        # EDIT FOR INSTRUMENT HERE ****
        if len(ser_line) == LINE_SIZE:
            try:
              line = ser_line.decode('utf-8')
            except:
              print (ESS_INSTR_NAME, ': Received line failed decode to utf-8. Ignoring received line')
            else:
                myData.TemperatureC01 = float(testVal(
                    PREAMBLE_1, line[0 * SENSOR_DATA_SIZE:1 * SENSOR_DATA_SIZE]))
                myData.TemperatureC02 = float(testVal(
                    PREAMBLE_2, line[1 * SENSOR_DATA_SIZE:2 * SENSOR_DATA_SIZE]))
                myData.TemperatureC03 = float(testVal(
                    PREAMBLE_3, line[2 * SENSOR_DATA_SIZE:3 * SENSOR_DATA_SIZE]))
                myData.TemperatureC04 = float(testVal(
                    PREAMBLE_4, line[3 * SENSOR_DATA_SIZE:4 * SENSOR_DATA_SIZE]))
        else:
            print (ESS_INSTR_NAME, ': Serial timeout with instrument or other error')

    # ----------------------------------------------------
    # SAL publish ....
    # **** EDIT FOR THIS INSTRUMENTS SAL ENTRY ****
    # ----------------------------------------------------
    def salTelemetryPublish(self):
        retval = self.mgr.putSample_Temperature4Ch(self.myData)
        if retval == 0:
            print (ESS_INSTR_NAME, ':', 'Published Temperature Ch1 =', self.myData.TemperatureC01)
            print (ESS_INSTR_NAME, ':', 'Published Temperature Ch2 =', self.myData.TemperatureC02)
            print (ESS_INSTR_NAME, ':', 'Published Temperature Ch3 =', self.myData.TemperatureC03)
            print (ESS_INSTR_NAME, ':', 'Published Temperature Ch4 =', self.myData.TemperatureC04)
        else:
            # TODO HANDLE SAL ERROR HERE ****
            print (ESS_INSTR_NAME, ':', 'SAL manager return value =', retval)

    def salTelemetryShutdown(self):
        print (ESS_INSTR_NAME,':', 'Shutting down')
        self.mgr.salShutdown()
        exit()








