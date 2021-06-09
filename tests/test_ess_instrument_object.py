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
import asyncio

from lsst.ts.ess.ess_instrument_object import EssInstrument
from lsst.ts.ess.sel_temperature_reader import SelTemperature
from lsst.ts.ess.mock.mock_temperature_sensor import MockTemperatureSensor


class EssInstrumentObjectTestCase(unittest.IsolatedAsyncioTestCase):
    async def _callback(self, data):
        self.assertEqual(self.num_channels + 3, len(data))
        for i in range(0, self.num_channels):
            data_item = data[i + 3]
            if self.nan_channel and i == self.nan_channel:
                self.assertAlmostEqual(9999.999, float(data_item), 3)
            else:
                self.assertLessEqual(MockTemperatureSensor.MIN_TEMP, float(data_item))
                self.assertLessEqual(float(data_item), MockTemperatureSensor.MAX_TEMP)
        self.ess_instrument._enabled = False

    async def test_ess_instrument_object(self):
        self.num_channels = 4
        self.nan_channel = None
        device = MockTemperatureSensor("MockSensor", self.num_channels)
        sel_temperature = SelTemperature("MockSensor", device, self.num_channels)
        await sel_temperature.start()
        self.ess_instrument = EssInstrument(
            "MockSensor", sel_temperature, callback_func=self._callback
        )
        self.ess_instrument._enabled = True
        await self.ess_instrument._run()

    async def test_old_ess_instrument_object(self):
        self.num_channels = 4
        count_offset = 1
        self.nan_channel = None
        device = MockTemperatureSensor("MockSensor", self.num_channels, count_offset)
        sel_temperature = SelTemperature("MockSensor", device, self.num_channels)
        await sel_temperature.start()
        self.ess_instrument = EssInstrument(
            "MockSensor", sel_temperature, callback_func=self._callback
        )
        self.ess_instrument._enabled = True
        await self.ess_instrument._run()

    async def test_nan_ess_instrument_object(self):
        self.num_channels = 4
        count_offset = 1
        self.nan_channel = 2
        device = MockTemperatureSensor(
            "MockSensor", self.num_channels, count_offset, self.nan_channel
        )
        sel_temperature = SelTemperature("MockSensor", device, self.num_channels)
        await sel_temperature.start()
        self.ess_instrument = EssInstrument(
            "MockSensor", sel_temperature, callback_func=self._callback
        )
        self.ess_instrument._enabled = True
        await self.ess_instrument._run()
