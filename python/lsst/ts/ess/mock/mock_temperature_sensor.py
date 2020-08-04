# This file is part of ts_ess.
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
import random


class MockTemperatureSensor:
    """Mock Temperature Sensor.
    """

    def __init__(self):
        # Instrument channel outputs
        self.temperature_c00 = None
        self.temperature_c01 = None
        self.temperature_c02 = None
        self.temperature_c03 = None

        self.log = logging.getLogger("MockTemperatureSensor")
        self.log.info("__init__")

    async def readInstrument(self):
        self.log.info("readInstrument")
        self.temperature_c00 = random.randint(180, 220) / 10.0
        self.temperature_c01 = random.randint(180, 220) / 10.0
        self.temperature_c02 = random.randint(180, 220) / 10.0
        self.temperature_c03 = random.randint(180, 220) / 10.0
