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
    def basic_make_csc(self, initial_state, config_dir, simulation_mode, **kwargs):
        logging.info("basic_make_csc")
        csc = ess.EssCsc(
            initial_state=initial_state,
            config_dir=config_dir,
            simulation_mode=simulation_mode,
            index=1,
        )
        return csc

    async def test_standard_state_transitions(self):
        logging.info("test_standard_state_transitions")
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.check_standard_state_transitions(
                enabled_commands=(),
            )

    async def test_version(self):
        logging.info("test_version")
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

    async def test_receive_telemetry(self):
        logging.info("test_receive_telemetry")
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            telemetry_topic = getattr(
                self.remote, f"tel_temperature{self.csc.config.channels}Ch"
            )
            data = await telemetry_topic.next(flush=False)
            print(data)
            for i in range(1, self.csc.config.channels + 1):
                temp_telemetry = getattr(data, f"temperatureC{i:02d}")
                self.assertTrue(MIN_TEMP <= temp_telemetry <= MAX_TEMP)

    async def test_receive_telemetry_with_nan(self):
        logging.info("test_receive_telemetry")
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            nan_channel = 1
            self.csc.nan_channel = nan_channel
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            telemetry_topic = getattr(
                self.remote, f"tel_temperature{self.csc.config.channels}Ch"
            )
            data = await telemetry_topic.next(flush=False)
            print(data)
            for i in range(1, self.csc.config.channels + 1):
                temp_telemetry = getattr(data, f"temperatureC{i:02d}")
                if i == nan_channel + 1:
                    self.assertAlmostEqual(9999.999, temp_telemetry, 3)
                else:
                    self.assertTrue(MIN_TEMP <= temp_telemetry <= MAX_TEMP)
