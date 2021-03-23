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

from lsst.ts.ess.mock.mock_temperature_sensor import (
    MockTemperatureSensor,
    MIN_TEMP,
    MAX_TEMP,
)


class MockTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_read_instrument(self):
        self.ess_sensor = MockTemperatureSensor("MockSensor", 4)
        self.ess_sensor.terminator = "\r\n"
        # Set the TAI time in the mock controller for easier control
        err, resp = self.ess_sensor.readline()
        resp = resp.strip(self.ess_sensor.terminator)
        data = resp.split(",")
        for i in range(0, 4):
            data_item = data[i].split("=")
            self.assertTrue(f"C{i:02d}", data_item[0])
            self.assertTrue(MIN_TEMP <= float(data_item[1]) <= MAX_TEMP)

    async def test_read_Old_instrument(self):
        count_offset = 1
        self.ess_sensor = MockTemperatureSensor("MockSensor", 4, count_offset)
        self.ess_sensor.terminator = "\r\n"
        # Set the TAI time in the mock controller for easier control
        err, resp = self.ess_sensor.readline()
        resp = resp.strip(self.ess_sensor.terminator)
        data = resp.split(",")
        for i in range(0, 4):
            data_item = data[i].split("=")
            self.assertTrue(f"C{i + count_offset:02d}", data_item[0])
            self.assertTrue(MIN_TEMP <= float(data_item[1]) <= MAX_TEMP)
