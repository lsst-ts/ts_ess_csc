# This file is part of ts_ess.
#
# Developed for the Vera C. Rubin Observatory Telescope and Site Systems.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

import logging
import time
from .sel_temperature_reader import SelTemperature
from .ess_instrument_object import EssInstrument
from .vcp_ftdi import VcpFtdi

logging.basicConfig(
    # Configure logging used for printing debug messages.
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.DEBUG,
    datefmt="%Y-%m-%d %H:%M:%S",
)


def callback(instrument, data_list):
    print(instrument.name, data_list)


# FTDI virtual comm port channel instance
INSTRUMENT_FTDI_SERIAL = "A601FT68"
ser_vcp_ch = VcpFtdi("FTDI_VCP", INSTRUMENT_FTDI_SERIAL)

# Reader instance: SEL temperature with six channels
SEL_INSTR_CH_CNT: int = 6
sel_temperature = SelTemperature("SelTemp", ser_vcp_ch, SEL_INSTR_CH_CNT)

# ESS instrument instance
ess_instr = EssInstrument("SelTemp_HatCh3", sel_temperature, callback)
ess_instr.start()

time.sleep(300)
ess_instr.stop()
