# This file is part of ts_ess_csc.
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
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
import logging
import math
import pathlib
import unittest

import numpy as np

from lsst.ts import salobj
from lsst.ts.ess import csc, common
from lsst.ts import tcpip


logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
    level=logging.DEBUG,
)

STD_TIMEOUT = 2  # standard command timeout (sec)
TEST_CONFIG_DIR = pathlib.Path(__file__).parents[1].joinpath("tests", "data", "config")


class CscTestCase(salobj.BaseCscTestCase, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.socket_server = common.SocketServer(
            name="EssCscTest", host=tcpip.LOCAL_HOST, port=0, simulation_mode=1
        )
        mock_command_handler = common.MockCommandHandler(
            callback=self.socket_server.write,
            simulation_mode=1,
        )
        self.socket_server.set_command_handler(mock_command_handler)
        await asyncio.wait_for(self.socket_server.start(), timeout=5)
        self.port = self.socket_server.port

    def basic_make_csc(
        self, initial_state, config_dir, simulation_mode, settings_to_apply="", **kwargs
    ):
        logging.info("basic_make_csc")
        ess_csc = csc.EssCsc(
            initial_state=initial_state,
            config_dir=config_dir,
            simulation_mode=simulation_mode,
            index=1,
            settings_to_apply=settings_to_apply,
        )
        return ess_csc

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
                cscVersion=csc.__version__,
                subsystemVersions="",
            )

    async def test_bin_script(self):
        logging.info("test_bin_script")
        await self.check_bin_script(name="ESS", index=1, exe_name="run_ess_csc.py")

    def create_reply_list(self, sensor_name, timestamp, additional_data):
        """Create a list that represents a reply from a sensor.

        Parameters
        ----------
        sensor_name: `str`
            The name of the sensor.
        timestamp: `float`
            The timestamp of the data.
        additional_data: `list`
            A list of additional data to add to the reply.
        Returns
        -------
        `list`
            A list formed by the sensor name, the timestamp, a ResponseCode and
            the additional data.
        """
        return [
            sensor_name,
            timestamp,
            common.ResponseCode.OK,
        ] + additional_data

    async def validate_telemetry(self):
        mtt = common.MockTestTools()
        for sensor_name in self.csc.device_configurations:
            md_props = common.MockDeviceProperties(name=sensor_name)
            device_config = self.csc.device_configurations[sensor_name]
            if device_config.sens_type == common.SensorType.TEMPERATURE:
                md_props.num_channels = device_config.num_channels
                data = await self.remote.tel_temperature.next(flush=False)

                # First make sure that the temperature data contain the
                # expected number of NaN values.
                expected_num_nans = len(data.temperature) - device_config.num_channels
                nan_array = [math.nan] * expected_num_nans
                np.testing.assert_array_equal(
                    nan_array, data.temperature[device_config.num_channels :]
                )

                # Next validate the rest of the data.
                assert data.numChannels == device_config.num_channels
                reply = self.create_reply_list(
                    sensor_name=data.sensorName,
                    timestamp=data.timestamp,
                    additional_data=data.temperature[: device_config.num_channels],
                )
                mtt.check_temperature_reply(md_props=md_props, reply=reply)
            elif device_config.sens_type == common.SensorType.HX85A:
                data = await self.remote.tel_hx85a.next(flush=False)
                reply = self.create_reply_list(
                    sensor_name=data.sensorName,
                    timestamp=data.timestamp,
                    additional_data=[
                        data.relativeHumidity,
                        data.temperature,
                        data.dewPoint,
                    ],
                )
                mtt.check_hx85a_reply(md_props=md_props, reply=reply)
            elif device_config.sens_type == common.SensorType.HX85BA:
                data = await self.remote.tel_hx85ba.next(flush=False)
                reply = self.create_reply_list(
                    sensor_name=data.sensorName,
                    timestamp=data.timestamp,
                    additional_data=[
                        data.relativeHumidity,
                        data.temperature,
                        data.barometricPressure,
                    ],
                )
                mtt.check_hx85ba_reply(md_props=md_props, reply=reply)
            else:
                raise ValueError(
                    f"Unsupported sensor type {device_config.sens_type} encountered."
                )

    async def test_receive_telemetry(self):
        logging.info("test_receive_telemetry")
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=TEST_CONFIG_DIR,
            simulation_mode=1,
        ):
            self.csc.port = self.port
            self.assertFalse(self.socket_server.connected)
            await salobj.set_summary_state(
                remote=self.remote,
                state=salobj.State.ENABLED,
                settingsToApply="test_all_sensors",
            )
            self.assertTrue(self.socket_server.connected)

            await self.validate_telemetry()

            await self.validate_telemetry()

            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.DISABLED
            )
            self.assertFalse(self.socket_server.connected)
            await self.socket_server.exit()
