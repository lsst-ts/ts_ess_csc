
import time
from vcp_ftdi import VCP_FTDI
from sel_temperature_reader import SEL_Temperature
from instrument_object import Instrument

def callback(data_list):
    print(data_list)

ser = VCP_FTDI('ser','A601FT68')
temp_rdr = SEL_Temperature('Temp_rdr', 6, ser)
instr = Instrument('Instr', temp_rdr, callback)

time.sleep(8)
instr.stop()
