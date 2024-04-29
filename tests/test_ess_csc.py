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
import functools
import logging
import pathlib
import types
import unittest
from unittest import mock

import astropy.units as u
import numpy as np
import yaml
from astropy.units import misc
from lsst.ts import salobj, tcpip, utils
from lsst.ts.ess import common, csc
from lsst.ts.ess.common.test_utils import MockTestTools
from lsst.ts.xml.enums.ESS import ErrorCode

STD_TIMEOUT = 10  # standard command timeout (sec)
TEST_CONFIG_DIR = pathlib.Path(__file__).parents[1].joinpath("tests", "data", "config")

# The communicate timeout to use in the ControllerDataClient timeout test (s).
COMMUNICATE_TIMEOUT = 2
# Long wait time for timeout tests (second).
LONG_WAIT_TIME = 8
# Too long wait time for timeout tests (second).
TOO_LONG_WAIT_TIME = 12
# The number of sensors when all sensors are used in the test.
NUM_ALL_SENSORS = 5
# The number os seconds to wait for a summary state change. This needs to be
# set to a sufficiently high number so the timeout tests don't fail.
STATE_TIMEOUT = 60

# Config override string to avoid duplication.
ALL_SENSORS_YAML = "test_all_sensors.yaml"


def create_reply_dict(
    sensor_name: str, additional_data: list[float | int]
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


def pa_to_mbar(value: float) -> float:
    """Convert a value in PA to a value in millibar.

    Parameters
    ----------
    value: `float`
        The value in Pa.

    Returns
    -------
    float
        The value in millibar.

    Notes
    -----
    All astropy S.I. units support prefixes like 'milli-'. Since 'bar' is a
    'misc' unit, it doesn't support prefixes. For millibar an exception was
    made and 'mbar' was added. See

    https://github.com/astropy/astropy/pull/7863

    This is not documented in the astropy documentation!
    """
    quantity_in_pa = value * u.Pa
    quantity_in_mbar = quantity_in_pa.to(misc.mbar)
    return quantity_in_mbar.value


class CscTestCase(salobj.BaseCscTestCase, unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        # Dict of topic attr_name: attr_data, where:
        # * attr_data is a dict of sensor_name: sensor_data
        # * sensor_data is a dict of timestamp: data
        # Set by topic_callback and read by next_data.
        self.data_dict: dict[str, dict[str, dict[float, salobj.BaseMsgType]]] = dict()
        # Event that is set by topic_callback and awaited by
        # next_data.
        self.data_event = asyncio.Event()
        self.validation_dispatch_dict = {
            common.SensorType.TEMPERATURE: self.validate_temperature_telemetry,
            common.SensorType.HX85A: self.validate_hx85a_telemetry,
            common.SensorType.HX85BA: self.validate_hx85ba_telemetry,
            common.SensorType.CSAT3B: self.validate_csat3b_telemetry,
            common.SensorType.WINDSONIC: self.validate_windsonic_telemetry,
        }

        super().setUp()

    def basic_make_csc(
        self,
        initial_state: salobj.State | int,
        config_dir: str | pathlib.Path | None,
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

    async def topic_callback(self, data: salobj.BaseMsgType, attr_name: str) -> None:
        """Callback for read topics.

        Assign to all topics for which you want to call next_data.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Data from a topic. Must have a sensorName field.
        attr_name : `str`
            Topic attribute name.
        """
        attr_data = self.data_dict.get(attr_name)
        if attr_data is None:
            self.data_dict[attr_name] = {data.sensorName: {data.timestamp: data}}
        else:
            sensor_data = attr_data.get(data.sensorName)
            if sensor_data is None:
                attr_data[data.sensorName] = {data.timestamp: data}
            else:
                sensor_data[data.timestamp] = data
        self.data_event.set()

    async def next_data(
        self,
        topics: list[salobj.topics.ReadTopic],
        sensor_name: str,
        timeout: float = STD_TIMEOUT,
    ) -> dict[str, salobj.BaseMsgType]:
        """Get data for a given set of topics.

        The data will all have the same sensor_name and timestamp
        (which is set to the timestamp of the most recent data found
        for the first topic).

        Wait for the data if not already available. The data is managed
        by topic_callback, so you must assign topic_callback as the callback
        for each topic for which you want data.

        Parameters
        ----------
        topics : `salobj.topics.ReadTopic`
            The topics to wait for. Each must have a ``sensorName`` field
            and have its callback set to `self.topic_callback`.
        sensor_name : `str`
            Required value of ``sensorName`` in the returned data.
        timeout : `float`
            Maximum time to wait, in seconds.

        Returns
        -------
        topic_data : `dict[str, salobj.BaseMsgType]`
            Data for each topic, as a dict of [topic attr_name: data].
        """
        return await asyncio.wait_for(
            self._next_data_impl(topics=topics, sensor_name=sensor_name),
            timeout=timeout,
        )

    async def _next_data_impl(
        self, topics: list[salobj.topics.ReadTopic], sensor_name: str
    ) -> dict[str, salobj.BaseMsgType]:
        """Implementation of next_data, without the timeout."""
        topics_data: dict[str, salobj.BaseMsgType] = dict()
        is_first = True
        while True:
            if len(topics_data) == len(topics):
                return topics_data
            if is_first:
                is_first = False
            else:
                self.data_event.clear()
                await self.data_event.wait()

            await self._loop_ver_topics(topics, sensor_name, topics_data)

    async def _loop_ver_topics(
        self,
        topics: list[salobj.topics.ReadTopic],
        sensor_name: str,
        topics_data: dict[str, salobj.BaseMsgType],
    ) -> None:
        timestamp = None
        for topic in topics:
            attr_data = self.data_dict.get(topic.attr_name, dict())
            if attr_data is None:
                # No data seen for this topic yet
                continue
            sensor_data = attr_data.get(sensor_name)
            if sensor_data is None:
                # No data seen for this sensor yet
                continue
            if timestamp is None:
                # This is the first topic read;
                # set timestamp to the timestamp of the
                # most recent data
                data = list(sensor_data.values())[-1]
                timestamp = data.timestamp
                topics_data[topic.attr_name] = data
            else:
                # Find data with the same timestamp
                # as the first topic read
                data = sensor_data.get(timestamp)
                if data is None:
                    # No data seen for this topic at the timestamp
                    continue
                topics_data[topic.attr_name] = data

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
        await self.check_bin_script(name="ESS", index=1, exe_name="run_ess_csc")

    async def validate_temperature_telemetry(
        self, device_config: types.SimpleNamespace, sensor_name: str
    ) -> None:
        num_channels = device_config.num_channels
        topics_data = await self.next_data(
            topics=[self.remote.tel_temperature], sensor_name=sensor_name
        )
        data = topics_data["tel_temperature"]

        # First make sure that the temperature data contain the
        # expected number of NaN values.
        expected_num_nans = len(data.temperatureItem) - device_config.num_channels
        nan_array = [np.nan] * expected_num_nans
        np.testing.assert_array_equal(
            nan_array, data.temperatureItem[device_config.num_channels :]
        )

        # Next validate the rest of the data.
        assert data.numChannels == device_config.num_channels
        assert data.location == device_config.location
        reply = create_reply_dict(
            sensor_name=data.sensorName,
            additional_data=data.temperatureItem[: device_config.num_channels],
        )
        mtt = MockTestTools()
        mtt.check_temperature_reply(
            reply=reply, name=sensor_name, num_channels=num_channels
        )

    async def validate_hx85a_telemetry(
        self, device_config: types.SimpleNamespace, sensor_name: str
    ) -> None:
        topics_data = await self.next_data(
            topics=[
                self.remote.tel_relativeHumidity,
                self.remote.tel_temperature,
                self.remote.tel_dewPoint,
            ],
            sensor_name=sensor_name,
        )
        reply = create_reply_dict(
            sensor_name=sensor_name,
            additional_data=[
                topics_data["tel_relativeHumidity"].relativeHumidityItem,
                topics_data["tel_temperature"].temperatureItem[0],
                topics_data["tel_dewPoint"].dewPointItem,
            ],
        )
        mtt = MockTestTools()
        mtt.check_hx85a_reply(reply=reply, name=sensor_name)

    async def validate_hx85ba_telemetry(
        self, device_config: types.SimpleNamespace, sensor_name: str
    ) -> None:
        topics_data = await self.next_data(
            topics=[
                self.remote.tel_relativeHumidity,
                self.remote.tel_temperature,
                self.remote.tel_pressure,
                self.remote.tel_dewPoint,
            ],
            sensor_name=sensor_name,
        )
        for attr_name in ("tel_temperature", "tel_pressure"):
            assert topics_data[attr_name].numChannels == 1

        # Convert the barometric pressure to a value in mbar because that is
        # what the check_hx85ba_reply method expects.
        reply = create_reply_dict(
            sensor_name=sensor_name,
            additional_data=[
                topics_data["tel_relativeHumidity"].relativeHumidityItem,
                topics_data["tel_temperature"].temperatureItem[0],
                pa_to_mbar(topics_data["tel_pressure"].pressureItem[0]),
                topics_data["tel_dewPoint"].dewPointItem,
            ],
        )
        mtt = MockTestTools()
        mtt.check_hx85ba_reply(reply=reply, name=sensor_name)

    async def validate_csat3b_telemetry(
        self, device_config: types.SimpleNamespace, sensor_name: str
    ) -> None:
        data = await self.remote.tel_airTurbulence.next(
            flush=False, timeout=STD_TIMEOUT
        )
        assert data.location == device_config.location
        record_counter = 1  # arbitrary value in range [0, 63]
        status = 0
        input_str = (
            f"{data.speed[0]}{data.speed[1]}{data.speed[2]},"
            f"{data.sonicTemperature},{status},{record_counter}"
        )
        signature = common.sensor.compute_signature(input_str, ",")
        reply = create_reply_dict(
            sensor_name=data.sensorName,
            additional_data=[
                data.speed[0],
                data.speed[1],
                data.speed[2],
                data.sonicTemperature,
                status,
                signature,
            ],
        )
        mtt = MockTestTools()
        mtt.check_csat3b_reply(reply=reply, name=sensor_name)

    def check_windsonic_telemetry(
        self,
        reply: common.test_utils.SensorReply,
        name: str,
        num_channels: int = 0,
        disconnected_channel: int = -1,
        missed_channels: int = 0,
        in_error_state: bool = False,
    ) -> None:
        device_name = reply["name"]
        time = float(reply["timestamp"])
        response_code = reply["response_code"]
        resp: list[float | int] = []
        assert len(reply["sensor_telemetry"]) == 2
        for i, value in enumerate(reply["sensor_telemetry"][0:2]):
            with self.subTest(i=i, value=value):
                assert isinstance(value, float) or isinstance(value, int)
        for value in reply["sensor_telemetry"]:
            resp.append(value)

        assert name == device_name
        assert time > 0
        if in_error_state:
            assert common.ResponseCode.DEVICE_READ_ERROR == response_code
        else:
            assert common.ResponseCode.OK == response_code
        assert common.device.MockWindSpeedConfig.min <= resp[0]
        assert resp[0] <= common.device.MockWindSpeedConfig.max
        assert common.device.MockDirectionConfig.min <= resp[1]
        assert resp[1] <= common.device.MockDirectionConfig.max

    async def validate_windsonic_telemetry(
        self, device_config: types.SimpleNamespace, sensor_name: str
    ) -> None:
        data = await self.remote.tel_airFlow.next(flush=False, timeout=STD_TIMEOUT)
        assert data.location == device_config.location
        # The check_windsonic_reply function in the ESS Common test utils only
        # validates the speed and direction and not the other values.
        reply = create_reply_dict(
            sensor_name=data.sensorName,
            additional_data=[data.speed, data.direction],
        )
        self.check_windsonic_telemetry(reply=reply, name=sensor_name)

    async def validate_telemetry(self) -> None:
        for topic in (
            self.remote.tel_relativeHumidity,
            self.remote.tel_temperature,
            self.remote.tel_dewPoint,
            self.remote.tel_pressure,
        ):
            topic.callback = functools.partial(
                self.topic_callback, attr_name=topic.attr_name
            )
        for data_client in self.csc.data_clients:
            for sensor_name, device_config in data_client.device_configurations.items():
                func = self.validation_dispatch_dict[device_config.sens_type]
                await func(device_config, sensor_name)

    async def test_receive_telemetry(self) -> None:
        logging.info("test_receive_telemetry")
        async with self.make_csc(
            initial_state=salobj.State.ENABLED,
            config_dir=TEST_CONFIG_DIR,
            simulation_mode=1,
            override=ALL_SENSORS_YAML,
        ):
            await self.assert_next_summary_state(
                salobj.State.ENABLED, timeout=STATE_TIMEOUT
            )
            assert len(self.csc.data_clients) == NUM_ALL_SENSORS
            for data_client in self.csc.data_clients:
                assert isinstance(data_client, common.data_client.ControllerDataClient)
                assert data_client.mock_controller.connected

            await self.validate_telemetry()

            await self.validate_telemetry()

            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.DISABLED
            )
            for data_client in self.csc.data_clients:
                assert not data_client.mock_controller.connected

    async def test_rpi_data_client_loses_connecton(self) -> None:
        """The CSC should fault when a ControllerDataClient loses its
        connection to the server.
        """
        async with self.make_csc(
            initial_state=salobj.State.ENABLED,
            config_dir=TEST_CONFIG_DIR,
            simulation_mode=1,
            override=ALL_SENSORS_YAML,
        ):
            await self.assert_next_summary_state(
                salobj.State.ENABLED, timeout=STATE_TIMEOUT
            )
            await self.assert_next_sample(topic=self.remote.evt_errorCode, errorCode=0)
            assert len(self.csc.data_clients) == NUM_ALL_SENSORS
            for data_client in self.csc.data_clients:
                assert data_client.mock_controller.connected

            # Disconnect one of the mock servers
            await self.csc.data_clients[1].mock_controller.close()

            await self.assert_next_summary_state(
                salobj.State.FAULT, timeout=STATE_TIMEOUT
            )
            await self.assert_next_sample(
                topic=self.remote.evt_errorCode, errorCode=ErrorCode.ConnectionLost
            )

    async def test_rpi_data_client_cannot_connect(self) -> None:
        """The CSC should fault if a ControllerDataClient cannot connect
        to the server.
        """
        # Start in DISABLED state so the data clients have been constructed,
        # but have not yet created and connecte to their mock servers.
        async with self.make_csc(
            initial_state=salobj.State.DISABLED,
            config_dir=TEST_CONFIG_DIR,
            simulation_mode=1,
            override=ALL_SENSORS_YAML,
        ):
            await self.assert_next_sample(topic=self.remote.evt_errorCode, errorCode=0)
            await self.assert_next_summary_state(
                salobj.State.DISABLED, timeout=STATE_TIMEOUT
            )

            # Prevent one of the data_clients from connecting,
            # then try to enable the CSC.
            assert len(self.csc.data_clients) == NUM_ALL_SENSORS
            for data_client in self.csc.data_clients:
                assert data_client.enable_mock_controller
            self.csc.data_clients[1].enable_mock_controller = False
            with salobj.assertRaisesAckError():
                await self.remote.cmd_enable.start(timeout=STD_TIMEOUT)
            await self.assert_next_summary_state(
                salobj.State.FAULT, timeout=STATE_TIMEOUT
            )
            await self.assert_next_sample(
                topic=self.remote.evt_errorCode, errorCode=ErrorCode.ConnectionFailed
            )

    @mock.patch(
        "lsst.ts.ess.common.data_client.controller_data_client.COMMUNICATE_TIMEOUT",
        COMMUNICATE_TIMEOUT,
    )
    async def test_rpi_data_client_timeout(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.ENABLED,
            config_dir=TEST_CONFIG_DIR,
            simulation_mode=1,
        ):
            await self.assert_next_summary_state(
                salobj.State.ENABLED, timeout=STATE_TIMEOUT
            )
            await self.assert_next_sample(topic=self.remote.evt_errorCode, errorCode=0)
            assert len(self.csc.data_clients) == 1
            for data_client in self.csc.data_clients:
                assert data_client.mock_controller.connected

            await self.validate_telemetry()

            # Set the wait time for the device to SHORT_WAIT_TIME, which is a
            # higher value than the default (see
            # lsst.ts.ess.common.device.MockDevice).
            common.device.MockDevice.telemetry_interval = LONG_WAIT_TIME

            # Here the default wait time still is used.
            await self.validate_telemetry()

            # Here SHORT_WAIT_TIME is used. This should NOT time out.
            await self.validate_telemetry()

            # Set the wait time for the device to LONG_WAIT_TIME, which is an
            # even higher value than the default (see
            # lsst.ts.ess.common.device.MockDevice).
            common.device.MockDevice.telemetry_interval = TOO_LONG_WAIT_TIME

            # Here SHORT_WAIT_TIME still is used.
            await self.validate_telemetry()

            # Here LONG_WAIT_TIME is used. This should time out.
            await self.assert_next_summary_state(
                salobj.State.FAULT, timeout=STATE_TIMEOUT
            )
            await self.assert_next_sample(
                topic=self.remote.evt_errorCode, errorCode=ErrorCode.ConnectionLost
            )

    async def test_restart_csc(self) -> None:
        """The CSC should NOT fault when the CSC is set to STANDBY and then to
        ENABLED again..
        """
        # Start the MockServer for manual control.
        await self.start_mock_controller()
        async with self.make_csc(
            initial_state=salobj.State.ENABLED,
            config_dir=TEST_CONFIG_DIR,
            simulation_mode=0,
            override="test_one_temp_sensor.yaml",
        ):
            await self.assert_next_summary_state(
                salobj.State.ENABLED, timeout=STATE_TIMEOUT
            )

            await self.assert_next_sample(topic=self.remote.evt_errorCode, errorCode=0)
            assert len(self.csc.data_clients) == 1

            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.STANDBY
            )
            await self.assert_next_summary_state(
                salobj.State.DISABLED, timeout=STATE_TIMEOUT
            )
            await self.assert_next_summary_state(
                salobj.State.STANDBY, timeout=STATE_TIMEOUT
            )

            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            await self.assert_next_summary_state(
                salobj.State.DISABLED, timeout=STATE_TIMEOUT
            )
            await self.assert_next_summary_state(
                salobj.State.ENABLED, timeout=STATE_TIMEOUT
            )

        # Stop the MockServer to clean up after ourselves.
        await self.stop_mock_controller()

    async def test_rpi_data_client_loses_connection(self) -> None:
        """Test timeouts of connections from the DataClient to the server.

        The CSC should fault when the DataClient loses its connection to the
        server and the DataClient should reconnect when the CSC is set to
        ENABLED again.
        """
        # Start the MockServer for manual control.
        await self.start_mock_controller()
        async with self.make_csc(
            initial_state=salobj.State.ENABLED,
            config_dir=TEST_CONFIG_DIR,
            simulation_mode=0,
            override="test_one_temp_sensor.yaml",
        ):
            await self.assert_next_summary_state(
                salobj.State.ENABLED, timeout=STATE_TIMEOUT
            )

            await self.assert_next_sample(topic=self.remote.evt_errorCode, errorCode=0)
            assert len(self.csc.data_clients) == 1

            # Stop the MockServer.
            await self.stop_mock_controller()
            await self.assert_next_summary_state(
                salobj.State.FAULT, timeout=STATE_TIMEOUT
            )

            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.STANDBY
            )
            await self.assert_next_summary_state(
                salobj.State.STANDBY, timeout=STATE_TIMEOUT
            )

            # Start the MockServer again.
            await self.start_mock_controller()

            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            await self.assert_next_summary_state(
                salobj.State.DISABLED, timeout=STATE_TIMEOUT
            )
            await self.assert_next_summary_state(
                salobj.State.ENABLED, timeout=STATE_TIMEOUT
            )

        # Stop the MockServer to clean up after ourselves.
        await self.stop_mock_controller()

    async def start_mock_controller(self) -> None:
        self.mock_controller = common.MockController(
            name="MockController",
            host=tcpip.LOCAL_HOST,
            port=5000,
            log=logging.getLogger("MockController"),
            simulation_mode=1,
        )
        mock_command_handler = common.MockCommandHandler(
            callback=self.mock_controller.write_json,
            simulation_mode=1,
        )
        self.mock_controller.set_command_handler(mock_command_handler)
        await asyncio.wait_for(self.mock_controller.start_task, timeout=STD_TIMEOUT)

    async def stop_mock_controller(self) -> None:
        await self.mock_controller.close()

    async def get_config_for_device(self, name: str) -> dict:
        config_file = TEST_CONFIG_DIR / "test_lightning_sensors.yaml"
        with open(config_file, "r") as f:
            config_raw_data = f.read()
            config = yaml.safe_load(config_raw_data)
            device_configs = config["instances"][0]["data_clients"][0]["config"][
                "devices"
            ]
            for device_config in device_configs:
                if device_config["name"] == name:
                    return device_config
        return dict()

    async def test_lightning_data_client_nominal(self) -> None:
        """The CSC should fault when a ControllerDataClient loses its
        connection to the server.
        """
        async with self.make_csc(
            initial_state=salobj.State.ENABLED,
            config_dir=TEST_CONFIG_DIR,
            simulation_mode=1,
            override="test_lightning_sensors.yaml",
        ):
            await self.assert_next_summary_state(
                salobj.State.ENABLED, timeout=STATE_TIMEOUT
            )

            # Verify that strike events and telemetry have been sent.
            data = await self.assert_next_sample(
                topic=self.remote.evt_lightningStrike,
                sensorName="EssLightning",
                bearing=0,
            )
            assert np.isinf(data.correctedDistance)
            assert np.isinf(data.uncorrectedDistance)
            await self.assert_next_sample(
                topic=self.remote.tel_lightningStrikeStatus,
                sensorName="EssLightning",
            )
            await self.assert_next_sample(
                topic=self.remote.evt_sensorStatus,
                sensorName="EssLightning",
            )

            # Verify that electric field events and telemetry have been sent.
            # Due to the accumulator and the device config, it takes a little
            # while until these events and telemetry get emitted.
            data = await self.assert_next_sample(
                topic=self.remote.tel_electricFieldStrength,
                sensorName="EssElectricField",
            )
            config = await self.get_config_for_device("EssElectricField")
            if np.abs(data.strengthMax) > config["threshold"]:
                await self.assert_next_sample(
                    topic=self.remote.evt_highElectricField,
                    sensorName="EssElectricField",
                )
            await self.assert_next_sample(
                topic=self.remote.evt_sensorStatus,
                sensorName="EssElectricField",
            )

    async def test_weather_station_data_client_timeout(self) -> None:
        """Test timeouts of connections from the DataClient to the server.

        The DataClient should reconnect automatically.
        """
        # Start the CSC in DISABLED mode for manual control of the DataClient.
        async with self.make_csc(
            initial_state=salobj.State.DISABLED,
            config_dir=TEST_CONFIG_DIR,
            simulation_mode=1,
            override="test_weather_station.yaml",
        ):
            await self.assert_next_summary_state(
                salobj.State.DISABLED, timeout=STATE_TIMEOUT
            )
            # Patch the "connect" method so we can count how often it was
            # called.
            with mock.patch.object(
                csc.Young32400WeatherStationDataClient,
                "connect",
                wraps=self.csc.data_clients[0].connect,
            ) as connect_mock:
                assert len(self.csc.data_clients) == 1
                assert self.csc.data_clients[0] is not None
                assert self.csc.data_clients[0].mock_data_server is None
                self.csc.data_clients[0].do_timeout = True
                # Not started yet so "connect" wasn't called yet.
                connect_mock.assert_not_called()

                await salobj.set_summary_state(
                    remote=self.remote, state=salobj.State.ENABLED
                )
                await self.assert_next_summary_state(
                    salobj.State.ENABLED, timeout=STATE_TIMEOUT
                )
                assert len(self.csc.data_clients) == 1
                assert self.csc.data_clients[0].mock_data_server is not None
                assert self.csc.data_clients[0].mock_data_server.connected
                # Started with a short timeout so "connect" was called several
                # times.
                connect_mock.assert_called()

                # Give the client time to recover from the timeout.
                await asyncio.sleep(2.0)
                # Recovered from the timeout such that "connect" should be
                # called at least 5 times, since the data client will attempt
                # to reconnect 5 times in case of a timeout.
                assert len(connect_mock.call_args_list) >= 5

    async def test_spectrum_analyzer_data_client_loses_connection(self) -> None:
        """Test timeouts of connections from the DataClient to the server.

        The CSC should fault when the DataClient loses its connection to the
        server and the DataClient should reconnect when the CSC is set to
        ENABLED again.
        """
        # Start the CSC in DISABLED mode for manual control of the DataClient.
        async with self.make_csc(
            initial_state=salobj.State.DISABLED,
            config_dir=TEST_CONFIG_DIR,
            simulation_mode=1,
            override="test_spectrum_analyzer_slow.yaml",
        ):
            await self.assert_next_summary_state(
                salobj.State.DISABLED, timeout=STATE_TIMEOUT
            )
            assert len(self.csc.data_clients) == 1
            assert self.csc.data_clients[0] is not None
            assert self.csc.data_clients[0].mock_data_server is None
            self.csc.data_clients[0].simulation_interval = LONG_WAIT_TIME

            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            await self.assert_next_summary_state(
                salobj.State.ENABLED, timeout=STATE_TIMEOUT
            )
            assert len(self.csc.data_clients) == 1
            assert self.csc.data_clients[0].mock_data_server is not None
            assert self.csc.data_clients[0].mock_data_server.connected

            # The CSC should go to FAULT state because of the long interval
            # between reading consecutive data.
            await self.assert_next_summary_state(
                salobj.State.FAULT, timeout=STATE_TIMEOUT
            )

    async def test_tcpip_data_client(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.ENABLED,
            config_dir=TEST_CONFIG_DIR,
            simulation_mode=0,
            override="tcpip_temperature_sensor.yaml",
        ):
            await self.assert_next_summary_state(
                salobj.State.ENABLED, timeout=STATE_TIMEOUT
            )
            assert len(self.csc.data_clients) == 1

            await self.assert_next_sample(
                topic=self.remote.evt_sensorStatus,
                sensorName="TcpipTemperature",
            )
            await self.assert_next_sample(
                topic=self.remote.tel_temperature,
                sensorName="TcpipTemperature",
            )
