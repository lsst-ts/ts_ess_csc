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

from lsst.ts.ess.mock.mock_anemometer import (
    MockAnemometer,
    MIN_DIRN,
    MAX_DIRN,
    MIN_SPEED,
    MAX_SPEED,
    LOW_WIND_SPEED,
)


class MockTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_read(self):
        NO_WIND = False
        ess_sensor = MockAnemometer("MockAnemometer", NO_WIND)
        ess_sensor.terminator = "\r\n"
        loop = asyncio.get_event_loop()
        err, resp = await loop.run_in_executor(None, ess_sensor.readline)
        resp = resp.strip(ess_sensor.terminator)
        csum = int(resp[-2:], 16)
        start = resp[0]
        end = resp[-3:-2]
        resp = resp[1:len(resp) - 3]
        checksum = 0
        for i in resp:
            checksum ^= ord(i)

        data = resp.split(",")
        self.assertTrue(err == "OK")
        self.assertTrue(start == "\x02")
        self.assertTrue(end == "\x03")
        self.assertTrue(data[0] == "Q")
        self.assertTrue(MIN_DIRN <= float(data[1]) <= MAX_DIRN)
        self.assertTrue(MIN_SPEED <= float(data[2]) <= MAX_SPEED)
        self.assertTrue(data[3] == "M")
        self.assertTrue(data[4] == "00")
        self.assertTrue(csum == checksum)

    async def test_read_nowind(self):
        NO_WIND = True
        ess_sensor = MockAnemometer("MockAnemometer", NO_WIND)
        ess_sensor.terminator = "\r\n"
        loop = asyncio.get_event_loop()
        err, resp = await loop.run_in_executor(None, ess_sensor.readline)
        resp = resp.strip(ess_sensor.terminator)
        csum = int(resp[-2:], 16)
        start = resp[0]
        end = resp[-3:-2]
        resp = resp[1:len(resp) - 3]
        checksum = 0
        for i in resp:
            checksum ^= ord(i)

        data = resp.split(",")
        self.assertTrue(err == "OK")
        self.assertTrue(start == "\x02")
        self.assertTrue(end == "\x03")
        self.assertTrue(data[0] == "Q")
        self.assertTrue(data[1] == "")
        self.assertTrue(MIN_SPEED <= float(data[2]) < LOW_WIND_SPEED)
        self.assertTrue(data[3] == "M")
        self.assertTrue(data[4] == "00")
        self.assertTrue(csum == checksum)

