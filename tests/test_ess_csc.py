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
import logging
import unittest

from lsst.ts import salobj
from lsst.ts import ess
from lsst.ts.envsensors import SocketServer, Temperature
from lsst.ts import tcpip


logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
    level=logging.DEBUG,
)


class CscTestCase(salobj.BaseCscTestCase, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.socket_server = SocketServer(
            host=tcpip.LOCAL_HOST, port=0, simulation_mode=1
        )
        await asyncio.wait_for(self.socket_server.start(), timeout=5)
        self.port = self.socket_server.port

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
            initial_state=salobj.State.STANDBY,
            config_dir=None,
            simulation_mode=1,
        ):
            self.csc.port = self.port
            await self.check_standard_state_transitions(
                enabled_commands=(),
            )

    async def test_version(self):
        logging.info("test_version")
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=None,
            simulation_mode=1,
        ):
            await self.assert_next_sample(
                self.remote.evt_softwareVersions,
                cscVersion=ess.__version__,
                subsystemVersions="",
            )

    async def test_bin_script(self):
        logging.info("test_bin_script")
        await self.check_bin_script(name="ESS", index=None, exe_name="run_ess.py")

    async def validate_telemetry(self, nan_channel=None):
        for sensor_name in self.csc.device_configurations:
            device_configuration = self.csc.device_configurations[sensor_name]
            telemetry_topic = getattr(
                self.remote, f"tel_temperature{device_configuration.channels}Ch"
            )
            data = await telemetry_topic.next(flush=False)
            for i in range(1, device_configuration.channels + 1):
                temp_telemetry = getattr(data, f"temperatureC{i:02d}")
                if nan_channel and i == nan_channel + 1:
                    self.assertAlmostEqual(9999.999, temp_telemetry, 3)
                else:
                    self.assertLessEqual(Temperature.MIN, temp_telemetry)
                    self.assertLessEqual(temp_telemetry, Temperature.MAX)

    async def test_receive_telemetry(self):
        logging.info("test_receive_telemetry")
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=None,
            simulation_mode=1,
        ):
            self.csc.port = self.port
            self.assertFalse(self.socket_server.connected)
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            self.assertTrue(self.socket_server.connected)
            await self.validate_telemetry()
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.DISABLED
            )
            self.assertFalse(self.socket_server.connected)
            await self.socket_server.exit()
