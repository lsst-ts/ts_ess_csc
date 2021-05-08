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
from lsst.ts.ess.vcp_ftdi import VcpFtdi
from lsst.ts.ess.rpi_serial_hat import RpiSerialHat


MIN_DIRN: float = 0
MAX_DIRN: float = 359
MIN_SPEED: float = 0.0
MAX_SPEED: float = 60.0


class AnemometerTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_anemometer_reader(self):
        device = RpiSerialHat("Ser", "serial_ch_3")
        anemometer = WindsonicAnemometer("Windsonic 60", device)

        await anemometer.start()
        for i in range(2):
            await anemometer.read()
        data = anemometer.output
        await anemometer.stop()
