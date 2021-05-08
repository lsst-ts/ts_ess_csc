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

from lsst.ts.ess.anemometer_reader import WindsonicAnemometer, DELIMITER

from lsst.ts.ess.mock.mock_anemometer import (
    MockAnemometer,
    MIN_DIRN,
    MAX_DIRN,
    MIN_SPEED,
    MAX_SPEED,
    LOW_WIND_SPEED,
)

DEFAULT_DIRECTION_VAL: float = 999
DEFAULT_SPEED_VAL: float = 9999.9990

class AnemometerTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_anemometer_reader(self):
        NO_WIND = False
        device = MockAnemometer("MockAnemometer", NO_WIND)
        anemometer = WindsonicAnemometer("Windsonic 60", device)

        await anemometer.start()
        await anemometer.read()
        data = anemometer.output
        self.assertTrue(data[1] == "OK")
        self.assertTrue(MIN_DIRN <= data[2] <= MAX_DIRN)
        self.assertTrue(MIN_SPEED <= data[3] <= MAX_SPEED)
        await anemometer.stop()

    async def test_anemometer_reader_nowind(self):
        NO_WIND = True
        device = MockAnemometer("MockAnemometer", NO_WIND)
        anemometer = WindsonicAnemometer("Windsonic 60", device)

        await anemometer.start()
        await anemometer.read()
        data = anemometer.output
        self.assertTrue(data[1] == "OK")
        self.assertTrue(data[2] == DEFAULT_DIRECTION_VAL)
        self.assertTrue(MIN_SPEED <= data[3] < LOW_WIND_SPEED)
        await anemometer.stop()
