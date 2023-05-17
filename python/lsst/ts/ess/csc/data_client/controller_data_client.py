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

__all__ = ["ControllerDataClient"]

import abc
import asyncio
import json
import logging
import types
import typing
from collections.abc import Sequence
from typing import Any, Callable

import jsonschema
from lsst.ts import salobj, tcpip
from lsst.ts.ess import common

# Time limit for connecting to the ESS Controller (seconds).
CONNECT_TIMEOUT = 5

# Timeout limit for communicating with the ESS Controller (seconds). This
# includes writing a command and reading the response and reading telemetry.
# Unit tests can set this to a lower value to speed up the test.
COMMUNICATE_TIMEOUT = 60


class ControllerDataClient(common.BaseReadLoopDataClient):
    """Get environmental data from sensors connected to an ESS Controller.

    Parameters
    ----------
    config : `types.SimpleNamespace`
        The configuration, after validation by the schema returned
        by `get_config_schema` and conversion to a types.SimpleNamespace.
    topics : `salobj.Controller` or `types.SimpleNamespace`
        The telemetry topics this data client can write,
        as a struct with attributes such as ``tel_temperature``.
    log : `logging.Logger`
        Logger.
    simulation_mode : `int`, optional
        Simulation mode; 0 for normal operation.
    """

    def __init__(
        self,
        config: types.SimpleNamespace,
        topics: salobj.Controller | types.SimpleNamespace,
        log: logging.Logger,
        simulation_mode: int = 0,
    ) -> None:
        # Dict of sensor_name: device configuration
        self.device_configurations: dict[str, common.DeviceConfig] = dict()

        # Lock for TCP/IP communication
        self.stream_lock = asyncio.Lock()

        # TCP/IP Client
        self.client: tcpip.Client | None = None

        # Set this attribute false before calling `start` to test failure
        # to connect to the server. Ignored if not simulating.
        self.enable_mock_server = True

        # Dict of SensorType: processing method
        self.telemetry_dispatch_dict: dict[
            str, Callable
        ] = self.get_telemetry_dispatch_dict()

        # Mock server for simulation mode
        self.mock_server = None

        super().__init__(
            config=config, topics=topics, log=log, simulation_mode=simulation_mode
        )
        self.configure()

        # Validator for JSON data.
        self.validator = jsonschema.Draft7Validator(schema=self.get_telemetry_schema())

    @abc.abstractmethod
    def get_telemetry_dispatch_dict(self) -> dict[str, Callable]:
        raise NotImplementedError()

    @classmethod
    @abc.abstractmethod
    def get_config_schema(cls) -> dict[str, Any]:
        """Get the config schema as jsonschema dict."""
        raise NotImplementedError()

    @classmethod
    def get_telemetry_schema(cls) -> dict[str, Any]:
        return json.loads(
            """
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "description": "Schema for Sensor Telemetry",
  "type": "object",
  "properties": {
    "telemetry": {
      "type": "object",
      "properties": {
        "name": {
          "description": "Name of the sensor.",
          "type": "string"
        },
        "timestamp": {
          "description": "Timestamp of the telemetry.",
          "type": "number"
        },
        "response_code": {
          "description": "Response code indicating if all is OK or if there is an error.",
          "type": "number"
        },
        "sensor_telemetry": {
          "description": "The sensor telemetry.",
          "type": "array",
          "minItems": 1
        }
      },
      "required": ["name", "timestamp", "response_code", "sensor_telemetry"],
      "additionalProperties": false
    }
  },
  "required": ["telemetry"],
  "additionalProperties": false
}
            """
        )

    @property
    def connected(self) -> bool:
        return self.client is not None and self.client.connected

    def configure(self) -> None:
        """Store device configurations.

        This provides easy access when processing telemetry.
        """
        for device in self.config.devices:
            if device[common.Key.DEVICE_TYPE] == common.DeviceType.FTDI:
                dev_id = common.Key.FTDI_ID
            elif device[common.Key.DEVICE_TYPE] == common.DeviceType.SERIAL:
                dev_id = common.Key.SERIAL_PORT
            else:
                raise RuntimeError(
                    f"Unknown device type {device[common.Key.DEVICE_TYPE]} encountered.",
                )
            num_channels = 0
            sensor_type = device[common.Key.SENSOR_TYPE]
            if sensor_type == common.SensorType.TEMPERATURE:
                num_channels = device[common.Key.CHANNELS]
            self.device_configurations[device[common.Key.NAME]] = common.DeviceConfig(
                name=device[common.Key.NAME],
                num_channels=num_channels,
                dev_type=device[common.Key.DEVICE_TYPE],
                dev_id=device[dev_id],
                sens_type=device[common.Key.SENSOR_TYPE],
                baud_rate=device[common.Key.BAUD_RATE],
                location=device.get(common.Key.LOCATION, "Location not specified."),
                num_samples=device.get(common.Key.NUM_SAMPLES, 0),
                safe_interval=device.get(common.Key.SAFE_INTERVAL, 0),
                threshold=device.get(common.Key.THRESHOLD, 0),
            )

    def descr(self) -> str:
        return f"host={self.config.host}, port={self.config.port}"

    async def connect(self) -> None:
        """Connect to the ESS Controller and configure it.

        Raises
        ------
        RuntimeError
            If already connected.
        """
        if self.connected:
            raise RuntimeError("Already connected.")

        if self.simulation_mode != 0:
            if self.enable_mock_server:
                self.mock_server = common.SocketServer(
                    name="MockDataServer",
                    host=tcpip.DEFAULT_LOCALHOST,
                    port=0,
                    log=self.log,
                    simulation_mode=1,
                )
                assert self.mock_server is not None  # make mypy happy
                mock_command_handler = common.MockCommandHandler(
                    callback=self.mock_server.write_json,
                    simulation_mode=1,
                )
                self.mock_server.set_command_handler(mock_command_handler)
                await asyncio.wait_for(
                    self.mock_server.start_task, timeout=CONNECT_TIMEOUT
                )
                # Change self.config instead of using a local variable
                # so descr and __repr__ show the correct host and port
                port = self.mock_server.port
            else:
                self.log.info(f"{self}.enable_mock_server false; connection will fail.")
                port = 0
            # Change self.config so descr and __repr__ show the actual
            # host and port.
            self.config.host = tcpip.LOCAL_HOST
            self.config.port = port

        self.client = tcpip.Client(
            host=self.config.host,
            port=self.config.port,
            log=self.log,
            name=type(self).__name__,
        )
        await asyncio.wait_for(fut=self.client.start_task, timeout=CONNECT_TIMEOUT)
        configuration = {common.Key.DEVICES: self.config.devices}
        await self.run_command(
            command=common.Command.CONFIGURE, configuration=configuration
        )

    async def disconnect(self) -> None:
        """Disconnect from the ESS Controller.

        Always safe to call, though it may raise asyncio.CancelledError
        if the client is currently being closed.
        """
        self.run_task.cancel()
        if self.connected:
            assert self.client is not None  # make mypy happy
            await self.client.close()
            self.client = None
        if self.mock_server is not None:
            await self.mock_server.close()

    async def read_data(self) -> None:
        """Read and process data from the ESS Controller."""
        async with self.stream_lock:
            assert self.client is not None  # keep mypy happy.
            data = await asyncio.wait_for(
                self.client.read_json(), timeout=COMMUNICATE_TIMEOUT
            )
        if common.Key.RESPONSE in data:
            self.log.warning("Read a command response with no command pending.")
        elif common.Key.TELEMETRY in data:
            self.log.debug(f"Processing {data}.")
            try:
                self.validator.validate(data)
                telemetry_data = data[common.Key.TELEMETRY]
                await self.process_telemetry(
                    sensor_name=telemetry_data[common.Key.NAME],
                    timestamp=telemetry_data[common.Key.TIMESTAMP],
                    response_code=telemetry_data[common.Key.RESPONSE_CODE],
                    sensor_data=telemetry_data[common.Key.SENSOR_TELEMETRY],
                )
            except Exception:
                self.log.exception(f"Exception processing {data}. Ignoring.")
        else:
            self.log.warning(f"Ignoring unparsable {data}.")

    async def run_command(self, command: str, **parameters: Any) -> None:
        """Write a command. Time out if it takes too long.

        Parameters
        ----------
        command : `str`
            The command to write.
        **parameters : `dict`
            Command parameters, as name=dict. For example::

                configuration = {"devices": self.config.devices}

        Raises
        ------
        ConnectionError
            If not connected.
        asyncio.TimeoutError
            If it takes more than COMMUNICATE_TIMEOUT seconds
            to acquire the lock or write the data.
        """
        data = {
            common.Key.COMMAND: command,
            common.Key.PARAMETERS: parameters,
        }
        await asyncio.wait_for(
            self._basic_run_command(data), timeout=COMMUNICATE_TIMEOUT
        )

    async def _basic_run_command(self, data: dict[str, typing.Any]) -> None:
        """Write a json-encoded command dict. Potentially wait forever.

        Parameters
        ----------
        data : `dict`[`str`, `typing.Any`]
            The data to write. The data should be of the form (but this is not
            verified)::

                {"command": command_str, "parameters": params_dict}

        Raises
        ------
        RuntimeError
            If the command fails.
        ConnectionError
            If disconnected before command is acknowledged.
        """
        async with self.stream_lock:
            if not self.connected:
                raise ConnectionError("Not connected; cannot send the command.")
            assert self.client is not None  # keep mypy happy.
            await self.client.write_json(data)
            while True:
                if not self.connected:
                    raise ConnectionError(
                        "Disconnected while waiting for command response."
                    )
                data = await self.client.read_json()
                if common.Key.RESPONSE in data:
                    response = data[common.Key.RESPONSE]
                    if response == common.ResponseCode.OK:
                        return
                    else:
                        raise RuntimeError(f"Command {data!r} failed: {response=!r}.")
                else:
                    self.log.debug("Ignoring non-command-ack.")

    async def process_telemetry(
        self,
        sensor_name: str,
        timestamp: float,
        response_code: int,
        sensor_data: Sequence[float | int | str],
    ) -> None:
        """Process the sensor telemetry.

        Parameters
        ----------
        sensor_name : `str`
            The name of the sensor.
        timestamp : `float`
            The timestamp of the data.
        response_code : `int`
            The response code.
        sensor_data : each of type `float`
            A Sequence of float representing the sensor telemetry data.

        Raises
        ------
        RuntimeError
            If the response code is common.ResponseCode.DEVICE_READ_ERROR
        """
        try:
            device_configuration = self.device_configurations.get(sensor_name)
            if device_configuration is None:
                raise RuntimeError(
                    f"No device configuration for sensor_name={sensor_name}."
                )
            if response_code == common.ResponseCode.OK:
                telemetry_method = self.telemetry_dispatch_dict.get(
                    device_configuration.sens_type
                )
                if telemetry_method is None:
                    raise RuntimeError(
                        f"Unsupported sensor type {device_configuration.sens_type}."
                    )
                await telemetry_method(
                    sensor_name=sensor_name,
                    timestamp=timestamp,
                    response_code=response_code,
                    sensor_data=sensor_data,
                )
            elif response_code == common.ResponseCode.DEVICE_READ_ERROR:
                raise RuntimeError(
                    f"Error reading sensor {sensor_name}. Please check the hardware."
                )
            else:
                self.log.warning(
                    f"Ignoring telemetry for sensor {sensor_name} "
                    f"with unknown response code {response_code}."
                )
        except Exception as e:
            self.log.exception(f"process_telemetry failed: {e!r}.")
            raise
