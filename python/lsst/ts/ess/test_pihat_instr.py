
import time
from sel_temperature_reader import SelTemperature
from ess_instrument_object import EssInstrument
from rpi_serial_hat import RpiSerialHat


def callback(instrument, data_list):
    print(instrument.name, data_list)


# RPi serial hat channel instance
ser_hat_ch = RpiSerialHat('SerialCh3', RpiSerialHat.SERIAL_CH_3)

# Reader instance: SEL temperature with six channels
SEL_INSTR_CH_CNT: int = 6
sel_temperature = SelTemperature('SelTemp', ser_hat_ch, SEL_INSTR_CH_CNT)

# ESS instrument instance
ess_instr = EssInstrument('SelTemp_HatCh3', sel_temperature, callback)

time.sleep(300)
ess_instr.stop()
