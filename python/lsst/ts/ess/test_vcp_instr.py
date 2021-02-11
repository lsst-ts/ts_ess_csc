
import time
from sel_temperature_reader import SelTemperature
from ess_instrument_object import EssInstrument
from vcp_ftdi import VcpFtdi


def callback(instrument, data_list):
    print(instrument.name, data_list)


# FTDI virtual comm port channel instance
INSTRUMENT_FTDI_SERIAL = 'A601FT68'
ser_vcp_ch = VcpFtdi('FTDI_VCP', INSTRUMENT_FTDI_SERIAL)

# Reader instance: SEL temperature with six channels
SEL_INSTR_CH_CNT: int = 6
sel_temperature = SelTemperature('SelTemp', ser_vcp_ch, SEL_INSTR_CH_CNT)

# ESS instrument instance
ess_instr = EssInstrument('SelTemp_HatCh3', sel_temperature, callback)

time.sleep(300)
ess_instr.stop()
