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
from typing import List, Union

import numpy as np

# TODO DM-32972 uncomment the following line,
# and remove `ErrorCode = csc.ess_csc.ErrorCode` below:
# from lsst.ts.idl.enums.ESS import ErrorCode
from lsst.ts.ess import common, csc
from lsst.ts import salobj
from lsst.ts import utils
from lsst.ts.ess.common.test_utils import MockTestTools


ErrorCode = csc.ess_csc.ErrorCode

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
    level=logging.DEBUG,
)

STD_TIMEOUT = 10  # standard command timeout (sec)
TEST_CONFIG_DIR = pathlib.Path(__file__).parents[1].joinpath("tests", "data", "config")


def create_reply_dict(
    sensor_name: str, additional_data: List[float]
) -> common.test_utils.SensorReply:
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
    return {
        common.Key.NAME: sensor_name,
        common.Key.TIMESTAMP: utils.current_tai(),
        common.Key.RESPONSE_CODE: common.ResponseCode.OK,
        common.Key.SENSOR_TELEMETRY: additional_data,
    }


class CscTestCase(salobj.BaseCscTestCase, unittest.IsolatedAsyncioTestCase):
    def basic_make_csc(
        self,
        initial_state: Union[salobj.State, int],
        config_dir: Union[str, pathlib.Path, None],
        index: int = 1,
        simulation_mode: int = 1,
        override: str = "",
    ) -> salobj.BaseCsc:
        logging.info("basic_make_csc")
        ess_csc = csc.EssCsc(
            initial_state=initial_state,
            config_dir=config_dir,
            simulation_mode=simulation_mode,
            index=index,
            override=override,
        )
        return ess_csc

    async def test_standard_state_transitions(self) -> None:
        logging.info("test_standard_state_transitions")
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=TEST_CONFIG_DIR,
            simulation_mode=1,
        ):
            await self.check_standard_state_transitions(enabled_commands=())

    async def test_version(self) -> None:
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

    async def test_bin_script(self) -> None:
        logging.info("test_bin_script")
        await self.check_bin_script(name="ESS", index=1, exe_name="run_ess_csc.py")

    async def validate_telemetry(self) -> None:
        print("validate telemetry")
        mtt = MockTestTools()
        for data_client in self.csc.data_clients:
            for sensor_name, device_config in data_client.device_configurations.items():
                name = sensor_name
                if device_config.sens_type == common.SensorType.TEMPERATURE:
                    num_channels = device_config.num_channels
                    data = await self.remote.tel_temperature.next(flush=False)

                    # First make sure that the temperature data contain the
                    # expected number of NaN values.
                    expected_num_nans = (
                        len(data.temperature) - device_config.num_channels
                    )
                    nan_array = [math.nan] * expected_num_nans
                    np.testing.assert_array_equal(
                        nan_array, data.temperature[device_config.num_channels :]
                    )

                    # Next validate the rest of the data.
                    assert data.numChannels == device_config.num_channels
                    assert data.location == device_config.location
                    reply = create_reply_dict(
                        sensor_name=data.sensorName,
                        additional_data=data.temperature[: device_config.num_channels],
                    )
                    mtt.check_temperature_reply(
                        reply=reply, name=name, num_channels=num_channels
                    )
                elif device_config.sens_type == common.SensorType.HX85A:
                    data = await self.remote.tel_hx85a.next(flush=False)
                    assert data.location == device_config.location
                    reply = create_reply_dict(
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
                    reply = create_reply_dict(
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

    async def test_receive_telemetry(self) -> None:
        logging.info("test_receive_telemetry")
        async with self.make_csc(
            initial_state=salobj.State.ENABLED,
            config_dir=TEST_CONFIG_DIR,
            simulation_mode=1,
            override="test_all_sensors.yaml",
        ):
            await self.assert_next_summary_state(salobj.State.ENABLED, timeout=2)
            assert len(self.csc.data_clients) == 3
            for data_client in self.csc.data_clients:
                assert isinstance(data_client, csc.RPiDataClient)
                assert data_client.mock_server.connected

            await self.validate_telemetry()

            await self.validate_telemetry()

            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.DISABLED
            )
            for data_client in self.csc.data_clients:
                assert not data_client.mock_server.connected

    async def test_rpi_data_client_loses_connecton(self) -> None:
        """The CSC should fault when an RPiDataClient loses its connection
        to the server.
        """
        async with self.make_csc(
            initial_state=salobj.State.ENABLED,
            config_dir=TEST_CONFIG_DIR,
            simulation_mode=1,
            override="test_all_sensors.yaml",
        ):
            await self.assert_next_summary_state(salobj.State.ENABLED)
            await self.assert_next_sample(topic=self.remote.evt_errorCode, errorCode=0)
            assert len(self.csc.data_clients) == 3
            for data_client in self.csc.data_clients:
                assert data_client.mock_server.connected

            # Disconnect one of the mock server
            await self.csc.data_clients[1].mock_server.exit()

            await self.assert_next_summary_state(salobj.State.FAULT)
            await self.assert_next_sample(
                topic=self.remote.evt_errorCode, errorCode=ErrorCode.ConnectionLost
            )

    async def test_rpi_data_client_cannot_connect(self) -> None:
        """The CSC should fault if an RPiDataClient cannot connect
        to the server.
        """
        # Start in DISABLED state so the data clients have been constructed,
        # but have not yet created and connecte to their mock servers.
        async with self.make_csc(
            initial_state=salobj.State.DISABLED,
            config_dir=TEST_CONFIG_DIR,
            simulation_mode=1,
            override="test_all_sensors.yaml",
        ):
            await self.assert_next_sample(topic=self.remote.evt_errorCode, errorCode=0)
            await self.assert_next_summary_state(salobj.State.DISABLED)

            # Prevent one of the data_clients from connecting,
            # then try to enable the CSC.
            assert len(self.csc.data_clients) == 3
            for data_client in self.csc.data_clients:
                assert data_client.enable_mock_server
            self.csc.data_clients[1].enable_mock_server = False
            with salobj.assertRaisesAckError():
                await self.remote.cmd_enable.start(timeout=STD_TIMEOUT)
            await self.assert_next_summary_state(salobj.State.FAULT)
            await self.assert_next_sample(
                topic=self.remote.evt_errorCode, errorCode=ErrorCode.ConnectionFailed
            )
