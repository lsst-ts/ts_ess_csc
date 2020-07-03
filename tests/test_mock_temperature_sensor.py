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

import asynctest
from asynctest.mock import CoroutineMock
import logging

from lsst.ts import salobj
from lsst.ts.ess.mock.mock_temperature_sensor import MockTemperatureSensor

logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG)


class MockTestCase(asynctest.TestCase):
    async def setUp(self):
        self.log = logging.getLogger("MockTestCase")
        self._ess_sensor = MockTemperatureSensor()
        # Replace the determine_current_tai method with a mock method so that
        # the current_tai value on the mock_ctrl object can be set to make sure
        # that the mock_ctrl object  behaves as if that amount of time has
        # passed.
        self._ess_sensor.determine_current_tai = CoroutineMock()

    async def test_read_instrument(self):
        # Set the TAI time in the mock controller for easier control
        self._ess_sensor.current_tai = salobj.current_tai()
        await self._ess_sensor.readInstrument()
        data = self._ess_sensor.myData
        self.assertEqual(self._ess_sensor.current_tai, data.timestamp)
