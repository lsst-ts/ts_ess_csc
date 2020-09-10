# *******************************************************************************
# File:         ess_start.py
# Date:         2020-09-08
# Author:       Garry Knight - Garry Knight, LLC
#
# Description:  LSST Environmental Sensors System (ESS) startup.
#               This script should be run immediately following system start.
#
# *******************************************************************************
import ess_temperature_reader

SCRIPT_NAME = 'ess_start'

'''
Initiate and run 4-channel temperature instrument thread using ttyUSB0.
This assumes that the instrument to be read is enumerated as ttyUSB0. This is
guaranteed if the instrument is the only virtual com port (VCP) device connected
to USB ports.
'''
ESS_TEMPERATURE_OBJECT_NAME: str = "ess_temp"
ESS_TEMPERATURE_CHANNELS = 6
ESS_TEMPERATURE_SERIAL_PORT: str = "/dev/ttyUSB0"
ESS_TEMPERATURE_SERIAL_BAUD: int = 19200
ESS_TEMPERATURE_SERIAL_TIMEOUT: float = 1.5

ess_temp = ess_temperature_reader.ESS_Temperature(
        ESS_TEMPERATURE_OBJECT_NAME,
        ESS_TEMPERATURE_CHANNELS,
        ESS_TEMPERATURE_SERIAL_PORT,
        ESS_TEMPERATURE_SERIAL_BAUD, 
        ESS_TEMPERATURE_SERIAL_TIMEOUT)

ess_temp._serial_open()
try:
    ess_temp.read_instrument()
except:
    pass
instr_thr = ess_temperature_reader.InstrumentThread("temp_loop1", ess_temp)

