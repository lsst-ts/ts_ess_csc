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

import logging
import math
import pathlib
import unittest

import numpy as np

from lsst.ts.idl.enums.ESS import ErrorCode
from lsst.ts.ess import csc, common
from lsst.ts import salobj
from lsst.ts import utils


logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
    level=logging.DEBUG,
)

STD_TIMEOUT = 10  # standard command timeout (sec)
TEST_CONFIG_DIR = pathlib.Path(__file__).parents[1].joinpath("tests", "data", "config")


def create_reply_list(sensor_name, additional_data):
    """Create a list that represents a reply from a sensor.

    Parameters
    ----------
    sensor_name: `str`
        The name of the sensor.
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
        utils.current_tai(),
        common.ResponseCode.OK,
    ] + additional_data


class CscTestCase(salobj.BaseCscTestCase, unittest.IsolatedAsyncioTestCase):
    def basic_make_csc(
        self,
        initial_state,
        config_dir,
        index=1,
        simulation_mode=1,
        settings_to_apply="",
    ):
        logging.info("basic_make_csc")
        ess_csc = csc.EssCsc(
            initial_state=initial_state,
            config_dir=config_dir,
            simulation_mode=simulation_mode,
            index=index,
            settings_to_apply=settings_to_apply,
        )
        return ess_csc

    def get_mock_server(self, index):
        """Get the mock server from the specified RPiModel model."""
        assert len(self.csc.models) > index
        model = self.csc.models[index]
        assert isinstance(model, csc.RPiModel)
        return model.mock_server

    async def test_standard_state_transitions(self):
        logging.info("test_standard_state_transitions")
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=None,
            simulation_mode=1,
        ):
            await self.check_standard_state_transitions(
                enabled_commands=(), settingsToApply="default.yaml"
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

    async def validate_telemetry(self):
        mtt = common.MockTestTools()
        for sensor_name in self.csc.device_configurations:
            name = sensor_name
            device_config = self.csc.device_configurations[sensor_name]
            if device_config.sens_type == common.SensorType.TEMPERATURE:
                num_channels = device_config.num_channels
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
                assert data.location == device_config.location
                reply = create_reply_list(
                    sensor_name=data.sensorName,
                    additional_data=data.temperature[: device_config.num_channels],
                )
                mtt.check_temperature_reply(
                    reply=reply, name=name, num_channels=num_channels
                )
            elif device_config.sens_type == common.SensorType.HX85A:
                data = await self.remote.tel_hx85a.next(flush=False)
                assert data.location == device_config.location
                reply = create_reply_list(
                    sensor_name=data.sensorName,
                    additional_data=[
                        data.relativeHumidity,
                        data.temperature,
                        data.dewPoint,
                    ],
                )
                mtt.check_hx85a_reply(reply=reply, name=name)
            elif device_config.sens_type == common.SensorType.HX85BA:
                data = await self.remote.tel_hx85ba.next(flush=False)
                assert data.location == device_config.location
                reply = create_reply_list(
                    sensor_name=data.sensorName,
                    additional_data=[
                        data.relativeHumidity,
                        data.temperature,
                        data.barometricPressure,
                        data.dewPoint,
                    ],
                )
                mtt.check_hx85ba_reply(reply=reply, name=name)
            else:
                raise ValueError(
                    f"Unsupported sensor type {device_config.sens_type} encountered."
                )

    async def test_receive_telemetry(self):
        logging.info("test_receive_telemetry")
        async with self.make_csc(
            initial_state=salobj.State.ENABLED,
            config_dir=TEST_CONFIG_DIR,
            simulation_mode=1,
            settings_to_apply="test_all_sensors.yaml",
        ):
            await self.assert_next_summary_state(salobj.State.ENABLED, timeout=2)
            assert len(self.csc.models) == 3
            for model in self.csc.models:
                assert isinstance(model, csc.RPiModel)
                assert model.mock_server.connected

            await self.validate_telemetry()

            await self.validate_telemetry()

            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.DISABLED
            )
            for model in self.csc.models:
                assert not model.mock_server.connected

    async def test_rpimodel_loses_connecton(self):
        """The CSC should fault when an RPiModel loses its connection
        to the server.
        """
        async with self.make_csc(
            initial_state=salobj.State.ENABLED,
            config_dir=TEST_CONFIG_DIR,
            simulation_mode=1,
            settings_to_apply="test_all_sensors.yaml",
        ):
            await self.assert_next_summary_state(salobj.State.ENABLED)
            assert len(self.csc.models) == 3
            for model in self.csc.models:
                assert model.mock_server.connected

            # Disconnect one of the mock server
            await self.csc.models[1].mock_server.exit()

            await self.assert_next_summary_state(salobj.State.FAULT)
            fault = await self.remote.evt_errorCode.next(
                flush=False, timeout=STD_TIMEOUT
            )
            # TODO: simplify error codes and pick the right one here.
            # # Due to the timing of the loops in the CSC, more than one
            # # ErrorCode may happen.
            assert fault.errorCode in set(ErrorCode)
            # assert fault.errorCode in {
            #     ErrorCode.NotConnected,
            #     ErrorCode.ReadLoopFailed,
            # }

    async def test_rpimodel_cannot_connect(self):
        """The CSC should fault if an RPiModel cannot connect
        to the server.
        """
        # Start in DISABLED state so the models have been constructed,
        # but have not yet created and connecte to their mock servers.
        async with self.make_csc(
            initial_state=salobj.State.DISABLED,
            config_dir=TEST_CONFIG_DIR,
            simulation_mode=1,
            settings_to_apply="test_all_sensors.yaml",
        ):
            await self.assert_next_summary_state(salobj.State.DISABLED)

            # Prevent one of the models from connecting,
            # then try to enable the CSC.
            assert len(self.csc.models) == 3
            for model in self.csc.models:
                assert model.enable_mock_server
            self.csc.models[1].enable_mock_server = False
            with salobj.assertRaisesAckError():
                await self.remote.cmd_enable.start(timeout=STD_TIMEOUT)
            await self.assert_next_summary_state(salobj.State.FAULT)

            fault = await self.remote.evt_errorCode.next(
                flush=False, timeout=STD_TIMEOUT
            )
            assert fault.errorCode in set(ErrorCode)
            # TODO: simplify error codes and pick the right one here.
            # assert fault.errorCode == ErrorCode.AlreadyConnected
