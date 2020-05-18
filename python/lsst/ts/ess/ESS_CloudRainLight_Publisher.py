# *******************************************************************************
# File:         ESS_CloudRainlight_publisher.py
# Date:         2020-05-11
# Author:       Garry Knight - Garry Knight, LLC
#
# Description:  LSST Environmental Sensors System (EAS) Cloud Rain Light
#               Instrument publisher using Service Abstraction Layer (SAL).
#               Written for Rapsberry Pi 4.
#
#               Provides an EAS instrument communication class and separate
#               thread controlling instrument read and publish to SAL thread.
#
# *******************************************************************************
import time

from SALPY_ESS import *
import serialhat

# Edit this name to SAL entry for this instrument ....
ESS_INSTR_NAME = 'ESS_CloudRainLight_Publisher'

ERR_VAL = -1999.999

# ----------------------------------------------------
# EAS Instrument Publisher class
#
# EDIT ONLY WHERE NOTED ****
# ----------------------------------------------------
class ESSInstrumentPublisher:

    def __init__(
            self,
            salid,
            uart = serialhat.UART2,
            baudrate = 9600,
            timeout = 1.0):

        self.name = ESS_INSTR_NAME
        self.uart = uart

        self.mgr = SAL_ESS(salid)
        self.mgr.salTelemetryPub('ESS_CloudRainLight')
        self.myData = ESS_CloudRainLightC()
                    
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
        if len(ser_line) > 40:
            try:
              line = ser_line.decode('utf-8')
            except:
              print (ESS_INSTR_NAME, ': Received line failed decode to utf-8. Ignoring received line')
            else:
                string_list = line.split(",")
                if len(string_list) == 12:
                    print (ESS_INSTR_NAME, ': Received Data List =', string_list)
                    # EDIT TO POPULATE SAL myData HERE ****
                    self.myData.AmbientTemperature = float(string_list[3]) / 100
                    self.myData.SkyTemperature = float(string_list[4]) / 100
                    self.myData.LightLevel = float(string_list[6])
                    self.myData.RainLevel = float(string_list[7])
                else:
                    # TODO Needs SAL error handling here ****
                    self.myData.AmbientTemperature = ERR_VAL
                    self.myData.SkyTemperature = ERR_VAL
                    self.myData.LightLevel = ERR_VAL
                    self.myData.RainLevel = ERR_VAL
                    print (ESS_INSTR_NAME, ': Missing data in line received from instrument')

        else:
            print (ESS_INSTR_NAME, ': Serial timeout with instrument or other error')

    # ----------------------------------------------------
    # SAL publish ....
    # **** EDIT FOR THIS INSTRUMENTS SAL ENTRY ****
    # ----------------------------------------------------
    def salTelemetryPublish(self):
        retval = self.mgr.putSample_CloudRainLight(self.myData)
        if retval == 0:
            print (ESS_INSTR_NAME, ':', 'Published Ambient Temp =', self.myData.AmbientTemperature)
            print (ESS_INSTR_NAME, ':', 'Published Sky Temp =' , self.myData.SkyTemperature)
            print (ESS_INSTR_NAME, ':', 'Published Light Level =', self.myData.LightLevel)
            print (ESS_INSTR_NAME, ':', 'Published Rain Level =', self.myData.RainLevel)
        else:
            # TODO HANDLE SAL ERROR HERE ****
            print (ESS_INSTR_NAME, ':', 'SAL manager return value =', retval)

    def salTelemetryShutdown(self):
        print (ESS_INSTR_NAME,':', 'Shutting down')
        self.mgr.salShutdown()
        exit()






