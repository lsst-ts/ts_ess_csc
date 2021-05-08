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

import unittest

from lsst.ts.ess.sel_temperature_reader import SelTemperature, DELIMITER
from lsst.ts.ess.vcp_ftdi import VcpFtdi

DEVICE_ID = "A10JZP7N"
#DEVICE_ID = "A10JZFA3"
#DEVICE_ID = "A601FT68"
NUM_CHANNELS = 6
MIN_TEMP = 0
MAX_TEMP = 9999.9990

class SelTemperatureReaderTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_sel_temperature_reader(self):
        device = VcpFtdi("Temp1", DEVICE_ID)
        sel_temperature = SelTemperature("SelTemp1", device, NUM_CHANNELS)
        await sel_temperature.start()
        # Read twice, since first read is almost guaranteed to be partial.
        await sel_temperature.read()
        await sel_temperature.read()
        data = sel_temperature.output
        self.assertEqual(NUM_CHANNELS + 2, len(data))
        for i in range(0, NUM_CHANNELS - 1):
            data_item = data[i + 2]
            self.assertTrue(MIN_TEMP <= float(data_item) <= MAX_TEMP)
        await sel_temperature.stop()
