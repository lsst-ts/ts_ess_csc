#!/usr/bin/env python

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

import asyncio
import logging

import numpy as np

from lsst.ts.ess.ess_instrument_object import EssInstrument
from lsst.ts.ess.sel_temperature_reader import SelTemperature
from lsst.ts.ess.vcp_ftdi import VcpFtdi

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
    level=logging.DEBUG,
)
log = logging.getLogger(__name__)

name = "EssTemperature4Ch"
channels = 4
ftdi_id = "AL05OBVR"


async def get_telemetry(output):
    try:
        log.debug(f"Getting the temperature from the sensor: {output}")
        data = {"timestamp": output[0]}
        error_code = output[1]
        if error_code == "OK":
            for i in range(2, 2 + channels):
                # The telemetry channels start counting at 1 and not 0.
                data[f"temperatureC{i - 1:02d}"] = (
                    float.nan if np.isnan(output[i]) else output[i]
                )
            log.info(f"Received temperatures {data}")
    except Exception:
        log.exception("Method get_temperature() failed")


async def main():
    device = VcpFtdi(name, ftdi_id, log)
    sel_temperature = SelTemperature(name, device, channels, log)
    ess_instrument = EssInstrument(name, sel_temperature, get_telemetry, log)
    await ess_instrument.start()


if __name__ == "__main__":
    logging.info("main")
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    try:
        loop.run_forever()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
