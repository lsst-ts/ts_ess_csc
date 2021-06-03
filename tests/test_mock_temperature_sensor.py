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
import unittest

from lsst.ts.ess.mock.mock_temperature_sensor import MockTemperatureSensor


class MockTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_read_instrument(self):
        num_channels = 4
        ess_sensor = MockTemperatureSensor("MockSensor", num_channels)
        ess_sensor.terminator = "\r\n"
        loop = asyncio.get_event_loop()
        name, err, resp = await loop.run_in_executor(None, ess_sensor.readline)
        resp = resp.strip(ess_sensor.terminator)
        data = resp.split(",")
        for i in range(0, num_channels):
            data_item = data[i].split("=")
            self.assertTrue(f"C{i:02d}", data_item[0])
            self.assertTrue(
                MockTemperatureSensor.MIN_TEMP
                <= float(data_item[1])
                <= MockTemperatureSensor.MAX_TEMP
            )

    async def test_read_old_instrument(self):
        num_channels = 4
        count_offset = 1
        ess_sensor = MockTemperatureSensor("MockSensor", num_channels, count_offset)
        ess_sensor.terminator = "\r\n"
        loop = asyncio.get_event_loop()
        name, err, resp = await loop.run_in_executor(None, ess_sensor.readline)
        resp = resp.strip(ess_sensor.terminator)
        data = resp.split(",")
        for i in range(0, num_channels):
            data_item = data[i].split("=")
            self.assertTrue(f"C{i + count_offset:02d}", data_item[0])
            self.assertTrue(
                MockTemperatureSensor.MIN_TEMP
                <= float(data_item[1])
                <= MockTemperatureSensor.MAX_TEMP
            )

    async def test_read_nan(self):
        num_channels = 4
        count_offset = 1
        nan_channel = 2
        ess_sensor = MockTemperatureSensor(
            "MockSensor", num_channels, count_offset, nan_channel
        )
        ess_sensor.terminator = "\r\n"
        loop = asyncio.get_event_loop()
        name, err, resp = await loop.run_in_executor(None, ess_sensor.readline)
        resp = resp.strip(ess_sensor.terminator)
        data = resp.split(",")
        for i in range(0, num_channels):
            data_item = data[i].split("=")
            self.assertTrue(f"C{i + count_offset:02d}", data_item[0])
            if i == nan_channel:
                self.assertTrue(data_item[1] == "9999.9990")
            else:
                self.assertTrue(
                    MockTemperatureSensor.MIN_TEMP
                    <= float(data_item[1])
                    <= MockTemperatureSensor.MAX_TEMP
                )
