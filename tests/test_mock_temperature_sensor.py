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

import asynctest
import logging

from lsst.ts.ess.mock.mock_temperature_sensor import MockTemperatureSensor

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG
)


class MockTestCase(asynctest.TestCase):
    async def setUp(self):
        self.log = logging.getLogger("MockTestCase")
        self._ess_sensor = MockTemperatureSensor()

    async def test_read_instrument(self):
        # Set the TAI time in the mock controller for easier control
        self._ess_sensor.read_instrument()
        self.assertTrue(
            18 <= self._ess_sensor.temperature[0] <= 22,
            f"temp = {self._ess_sensor.temperature[0]}",
        )
        self.assertTrue(
            18 <= self._ess_sensor.temperature[1] <= 22,
            f"temp = {self._ess_sensor.temperature[1]}",
        )
        self.assertTrue(
            18 <= self._ess_sensor.temperature[2] <= 22,
            f"temp = {self._ess_sensor.temperature[2]}",
        )
        self.assertTrue(
            18 <= self._ess_sensor.temperature[3] <= 22,
            f"temp = {self._ess_sensor.temperature[3]}",
        )
