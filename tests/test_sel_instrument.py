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

MIN_TEMP: float = 20.0
MAX_TEMP: float = 30.0


class SelInstrumentTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_sel_instrument(self):
        num_channels = 6
        ftdi_serial: str = "A601FT68"
        device = VcpFtdi("FTDI_VCP", ftdi_serial)

        sel_temperature = SelTemperature("SEL1405", device, num_channels)
        await sel_temperature.start()
        await sel_temperature.read()
        await sel_temperature.read()
        data = sel_temperature.output
        nan_channels = [False, True, True, True, True, True]
        self.assertEqual(num_channels + 2, len(data))
        for i in range(0, num_channels):
            data_item = data[i + 2]
            if nan_channels[i] == True:
                self.assertAlmostEqual(9999.999, float(data_item), 3)
            else:
                self.assertTrue(MIN_TEMP <= float(data_item) <= MAX_TEMP)
        await sel_temperature.stop()
