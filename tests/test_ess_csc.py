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

import logging
import unittest

from lsst.ts import salobj
from lsst.ts import ess
from lsst.ts.ess.mock.mock_temperature_sensor import MIN_TEMP, MAX_TEMP


class CscTestCase(salobj.BaseCscTestCase, unittest.IsolatedAsyncioTestCase):
    def get_telemetry(self, output):
        """This function makes sure that the loop in ess_instrument gets
        canceled as soon as the first data have arrived to avoid an endless
        loop."""
        print(output)
        self.assertEqual(self.num_channels + 2, len(output))
        self.ess_instrument._enabled = False
        for i in range(0, 4):
            data_item = output[i + 2]
            self.assertTrue(MIN_TEMP <= float(data_item) <= MAX_TEMP)

    def basic_make_csc(self, initial_state, config_dir, simulation_mode, **kwargs):
        logging.info("basic_make_csc")
        csc = ess.EssCsc(
            initial_state=initial_state,
            config_dir=config_dir,
            simulation_mode=simulation_mode,
        )
        # shameless monkey patch
        csc.get_telemetry = self.get_telemetry
        return csc

    async def test_standard_state_transitions(self):
        logging.info("test_standard_state_transitions")
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.check_standard_state_transitions(enabled_commands=(),)

    async def test_version(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.assert_next_sample(
                self.remote.evt_softwareVersions,
                cscVersion=ess.__version__,
                subsystemVersions="",
            )

    async def test_bin_script(self):
        logging.info("test_bin_script")
        await self.check_bin_script(name="ESS", index=None, exe_name="run_ess.py")
