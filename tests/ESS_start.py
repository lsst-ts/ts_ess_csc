# *******************************************************************************
# File:         ESS_start.py
# Date:         2020-07-24
# Author:       Garry Knight - Garry Knight, LLC
#
# Description:  LSST Environmental Sensors System (ESS) startup.
#               This script should be run immediately following system start.
#
# *******************************************************************************
import ESS_temperature_4ch_reader

SCRIPT_NAME = 'ESS_start'

'''
Initiate and run 4-channel temperature instrument thread using ttyUSB0.
This assumes that the instrument to be read is enumerated as ttyUSB0. This is
guaranteed if the instrument is the only virtual com port (VCP) device connected
to USB ports.
'''
ESS_Temp4 = ESS_temperature_4ch_reader.ESS_Temperature_4ch('/dev/ttyUSB0', 19200, 1.5)
ESS_Temp4.serial_open()
instrThr = ESS_temperature_4ch_reader.instrumentThread('thrd', ESS_Temp4)
instrThr.run()
ESS_temp4.serial_close()

