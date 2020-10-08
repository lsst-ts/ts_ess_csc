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

from lsst.ts import salobj


class MockTemperatureSensor:
    """Mock Temperature Sensor."""

    def __init__(self):
        # Timestamp
        self.timestamp: float = None
        # Instrument channel outputs
        self.temperature: float = [0.0, 0.0, 0.0, 0.0]

        self.log = logging.getLogger("MockTemperatureSensor")
        self.log.info("__init__")

    def read_instrument(self):
        self.log.info("read_instrument")
        self.timestamp = salobj.current_tai
        self.temperature[0] = random.randint(180, 220) / 10.0
        self.temperature[1] = random.randint(180, 220) / 10.0
        self.temperature[2] = random.randint(180, 220) / 10.0
        self.temperature[3] = random.randint(180, 220) / 10.0
