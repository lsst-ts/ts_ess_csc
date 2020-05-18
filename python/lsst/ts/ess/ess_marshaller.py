# *******************************************************************************
# File:      essmarshaller.py
# Date:      2020-05-03
# Author:    Garry Knight - Garry Knight, LLC for LSST
#
# Description:  Provides selection of sensor types and allocates serial ports
#		for use with RPi4 only.
#		Configuration is provided for use as either SAL Publisher
#		or Subscriber.
#		This script also determines use with or without the LSST
#		designed Serial PoE hat.
#		The Serial PoE hat provides control of up to five
#		isolated serial interfaces as follows:
#			UART1 - RS-422
#			UART2 - RS-232
#			UART3 - RS-232
#			UART4 - RS-232
#			UART5 - RS-422
#		Classes for the Serial PoE hat are provided by serialhat.py.
#
#		Configuration is provided by the 'ess_config.conf' using
#		configparser. The configuration includes SAL ID for the RPi node,
#		existence of serial hat and configuration of uarts/sensors.
#
# *******************************************************************************

import threading
import time
from pathlib import Path
import configparser
from SALPY_ESS import *
import serialhat
import importlib

SCRIPT_NAME = 'essmarshaller.py :'

serial_poe_hat_installed = False

#-----------------------------------------------------------------------------
# Test for script file exists
#-----------------------------------------------------------------------------
def IsScript(filename = ''):
    if Path(filename).is_file():
        return True
    else:
        return False

#-----------------------------------------------------------------------------
# Instrument thread class ....
#-----------------------------------------------------------------------------
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
            self.ess_instrument.salTelemetryPublish()
            time.sleep(0.5)
            self.counter = self.counter + 1
            print(self.ess_instrument.name, ':', 'Running thread:', self.threadID, 'Count:', self.counter)

# ----------------------------------------------------

# Load the configuration ....
print(SCRIPT_NAME, 'ESS UART/Sensor Marshaller Started.')
print(SCRIPT_NAME, 'Loading Configuration ....')
cfg = configparser.ConfigParser()

if cfg.read('ess_config.conf') != []:
    print(SCRIPT_NAME, 'Node Configuration loaded .....')
    for key in cfg.sections():
        print('   ',key)
        for item in cfg[key]:
            print('       ', item, '=', cfg[key][item])
else:
    print(SCRIPT_NAME, 'Configuration file not found. Exiting ...')
    exit

# Test and implement SAL ID > 0 ....
if cfg.has_section('SAL'):
    ESS_SAL_Identifier = cfg.getint('SAL', 'ess_sal_id')
    if ESS_SAL_Identifier > 0:
        print (SCRIPT_NAME, 'ESS_SAL_Identifier =', ESS_SAL_Identifier)
    else:
        print (SCRIPT_NAME, 'Invalid SAL Identifier or not found. Exiting ...')
        exit
else:
    print (SCRIPT_NAME, '[SAL] configuration section not found. Exiting ...')
    exit

# Test and implement Hardware configuration ....
if cfg.has_section('Hardware'):
    if cfg['Hardware']['serialpoehat_installed'] == 'True':
        serial_poe_hat_installed = True
        print (SCRIPT_NAME, 'serialpoehat_installed = True')
        # Intialize hat serial modules ....
#        serialhat.SerialHat_init()
    else:
        print (SCRIPT_NAME, 'serialpoehat_installed = False')

    if cfg.has_section('SerialPorts') and len(cfg['SerialPorts']) == 5:

        port1_settings = cfg['SerialPorts']['port1'].split(',')
        port2_settings = cfg['SerialPorts']['port2'].split(',')
        port3_settings = cfg['SerialPorts']['port3'].split(',')
        port4_settings = cfg['SerialPorts']['port4'].split(',')
        port5_settings = cfg['SerialPorts']['port5'].split(',')

        ESS_SCRIPT_NAME = 0
        BAUD = 1
        TIMEOUT = 2

        print (SCRIPT_NAME, 'Port1 settings:', port1_settings[ESS_SCRIPT_NAME], port1_settings[BAUD], port1_settings[TIMEOUT])
        print (SCRIPT_NAME, 'Port2 settings:', port2_settings[ESS_SCRIPT_NAME], port2_settings[BAUD], port2_settings[TIMEOUT])
        print (SCRIPT_NAME, 'Port3 settings:', port3_settings[ESS_SCRIPT_NAME], port3_settings[BAUD], port3_settings[TIMEOUT])
        print (SCRIPT_NAME, 'Port4 settings:', port4_settings[ESS_SCRIPT_NAME], port4_settings[BAUD], port4_settings[TIMEOUT])
        print (SCRIPT_NAME, 'Port5 settings:', port5_settings[ESS_SCRIPT_NAME], port5_settings[BAUD], port5_settings[TIMEOUT])

        if serial_poe_hat_installed == True:
            # Test for interface script, setup and initialize Serial 
            # PoE Hat modules and import instrument scripts ....
            # Port 1 uses RS-422 Module1 (U4) and UART0 of RPi4
            if IsScript(port1_settings[ESS_SCRIPT_NAME] + '.py') == True:

                port1_instrument_module = importlib.import_module(port1_settings[ESS_SCRIPT_NAME])
                baudrate = int(port1_settings[BAUD])
                timeout = float(port1_settings[TIMEOUT])
                port1_instrument = port1_instrument_module.ESSInstrumentPublisher(
                                        ESS_SAL_Identifier,
                                        serialhat.UART0,
                                        baudrate,
                                        timeout)
                eas_instrument_thread1 = instrumentThread('Port1_thread', port1_instrument)
                eas_instrument_thread1.start()
            else:
                print (SCRIPT_NAME, 'Port 1 - ESS SAL publisher script not found.')

            # Port 2 uses channel 1 of RS-232 Module2 (U5) and UART2 of RPi4
            if IsScript(port2_settings[ESS_SCRIPT_NAME] + '.py') == True:

                port2_instrument_module = importlib.import_module(port2_settings[ESS_SCRIPT_NAME])
                baudrate = int(port2_settings[BAUD])
                timeout = float(port2_settings[TIMEOUT])
                port2_instrument = port2_instrument_module.ESSInstrumentPublisher(
                                        ESS_SAL_Identifier,
                                        serialhat.UART2,
                                        baudrate,
                                        timeout)
                eas_instrument_thread2 = instrumentThread('Port2_thread', port2_instrument)
                eas_instrument_thread2.start()
            else:
                print (SCRIPT_NAME, 'Port 2 - ESS SAL publisher script not found.')

                
            # Port 3 uses channel 2 of RS-232 Module2 (U5) and UART3 of RPi4
            if IsScript(port3_settings[ESS_SCRIPT_NAME] + '.py') == True:

                port3_instrument_module = importlib.import_module(port3_settings[ESS_SCRIPT_NAME])
                baudrate = int(port3_settings[BAUD])
                timeout = float(port3_settings[TIMEOUT])
                port3_instrument = port3_instrument_module.ESSInstrumentPublisher(
                                        ESS_SAL_Identifier,
                                        serialhat.UART3,
                                        baudrate,
                                        timeout)
                eas_instrument_thread3 = instrumentThread('Port3_thread', port3_instrument)
                eas_instrument_thread3.start()
            else:
                print (SCRIPT_NAME, 'Port 3 - ESS SAL publisher script not found.')

            # Port 4 uses channel 1 of RS-232 Module3 (U6) and UART1 of RPi4
            if IsScript(port4_settings[ESS_SCRIPT_NAME] + '.py') == True:

                port4_instrument_module = importlib.import_module(port4_settings[ESS_SCRIPT_NAME])
                baudrate = int(port4_settings[BAUD])
                timeout = float(port4_settings[TIMEOUT])
                port4_instrument = port4_instrument_module.ESSInstrumentPublisher(
                                        ESS_SAL_Identifier,
                                        serialhat.UART1,
                                        baudrate,
                                        timeout)
                eas_instrument_thread4 = port4_instrument_module.instrumentThread('Port4_thread', port4_instrument)
                eas_instrument_thread4.start()
            else:
                print (SCRIPT_NAME, 'Port 4 - ESS SAL publisher script not found.')

            # Port 5 uses channel 2 of RS-232 Module3 (U6) and UART4 of RPi4
            if IsScript(port5_settings[ESS_SCRIPT_NAME] + '.py') == True:

                port5_instrument_module = importlib.import_module(port5_settings[ESS_SCRIPT_NAME])
                baudrate = int(port5_settings[BAUD])
                timeout = float(port5_settings[TIMEOUT])
                port5_instrument = port5_instrument_module.ESSInstrumentPublisher(
                                        ESS_SAL_Identifier,
                                        serialhat.UART4,
                                        baudrate,
                                        timeout)
                eas_instrument_thread5 = instrumentThread('Port5_thread', port5_instrument)
                eas_instrument_thread5.start()
            else:
                print (SCRIPT_NAME, 'Port 5 - ESS SAL publisher script not found.')
                exit
    else:
        print (SCRIPT_NAME, '[SerialPorts] five allocations not found. Exiting ...')
        exit
else:
    print (SCRIPT_NAME, '[Hardware] configuration section not found. Exiting ...')
    exit

