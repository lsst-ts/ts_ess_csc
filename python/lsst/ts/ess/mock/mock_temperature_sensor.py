# This file is part of ts_Dome.
#
# Developed for the LSST Data Management System.
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
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

__all__ = ["MockTemperatureSensor"]

import logging

from lsst.ts import salobj
from lsst.ts.ess.mock.ess_temperature_4ch_c import EssTemperature4ChC


class MockTemperatureSensor:
    """Mock Temperature Sensor.
    """

    def __init__(self):
        self.myData = EssTemperature4ChC()
        # Time keeping
        self.current_tai = 0
        self.previous_tai = 0
        self.log = logging.getLogger("MockTemperatureSensor")
        self.log.info("__init__")

    async def readInstrument(self):
        self.log.info("readInstrument")
        # Mock the behavior that the temperature data are only updated by the
        # real sensors every 1 second.
        await self.determine_current_tai()
        if self.current_tai - self.previous_tai > 1.0:
            self.myData.timestamp = self.current_tai
            self.myData.TemperatureC01 = 20.0
            self.myData.TemperatureC02 = 20.1
            self.myData.TemperatureC03 = 19.9
            self.myData.TemperatureC04 = 20.2
            self.previous_tai = self.current_tai

    async def determine_current_tai(self):
        """Determine the current TAI time.

        This is done in a separate method so a mock method can replace it in
        unit tests.
        """
        self.current_tai = salobj.current_tai()
