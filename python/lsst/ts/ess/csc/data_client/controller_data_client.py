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
from collections.abc import Sequence
from typing import Any, Callable

import jsonschema
from lsst.ts import salobj, tcpip
from lsst.ts.ess import common

# Time limit for connecting to the Controller (seconds).
CONNECT_TIMEOUT = 5

# The maximum number of timeouts to allow before raising a TimeoutError.
MAX_ALLOWED_READ_TIMEOUTS = 5

# Timeout limit for communicating with the RPi (seconds). This includes
# writing a command and reading the response and reading telemetry. Unit
# tests can set this to a lower value to speed up the test.
COMMUNICATE_TIMEOUT = 60


class ControllerDataClient(common.BaseDataClient):
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

        # TCP/IP stream reader and writer
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None

        # Set this attribute false before calling `start` to test failure
        # to connect to the server. Ignored if not simulating.
        self.enable_mock_server = True

        # Dict of SensorType: processing method
        self.telemetry_dispatch_dict: dict[
            str, Callable
        ] = self.get_telemetry_dispatch_dict()

        # Mock server for simulation mode
        self.mock_server = None

        # Number of consecutive read timeouts encountered.
        self.num_consecutive_read_timeouts = 0

        super().__init__(
            config=config, topics=topics, log=log, simulation_mode=simulation_mode
        )
        self.configure()

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
        return not (
            self.reader is None
            or self.writer is None
            or self.reader.at_eof()
            or self.writer.is_closing()
        )

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
        """Connect to the RPi and configure it.

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
                    name="MockRPiServer",
                    host=tcpip.LOCAL_HOST,
                    port=0,
                    simulation_mode=1,
                )
                assert self.mock_server is not None  # make mypy happy
                mock_command_handler = common.MockCommandHandler(
                    callback=self.mock_server.write,
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
                self.log.info(f"{self}.enable_mock_server false; connection will fail")
                port = 0
            # Change self.config so descr and __repr__ show the actual
            # host and port.
            self.config.host = tcpip.LOCAL_HOST
            self.config.port = port

        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(
                host=self.config.host, port=self.config.port
            ),  # type: ignore
            timeout=CONNECT_TIMEOUT,
        )
        configuration = {"devices": self.config.devices}
        await self.run_command(command="configure", configuration=configuration)

    async def disconnect(self) -> None:
        """Disconnect from the RPi.

        Always safe to call, though it may raise asyncio.CancelledError
        if the writer is currently being closed.
        """
        if self.connected:
            await asyncio.wait_for(
                tcpip.close_stream_writer(self.writer), timeout=CONNECT_TIMEOUT
            )
        if self.mock_server is not None:
            await self.mock_server.close()

    async def run(self) -> None:
        """Read and process data from the RPi."""
        validator = jsonschema.Draft7Validator(schema=self.get_telemetry_schema())
        while self.connected:
            try:
                async with self.stream_lock:
                    data = await self.read()
                    # Reset the number of consecutive timouts since no timeout
                    # happend.
                    self.num_consecutive_read_timeouts = 0
                if common.Key.RESPONSE in data:
                    self.log.warning("Read a command response with no command pending")
                elif common.Key.TELEMETRY in data:
                    self.log.debug(f"Processing data {data}")
                    try:
                        validator.validate(data)
                    except Exception as e:
                        raise RuntimeError(e)
                    telemetry_data = data[common.Key.TELEMETRY]
                    await self.process_telemetry(
                        sensor_name=telemetry_data[common.Key.NAME],
                        timestamp=telemetry_data[common.Key.TIMESTAMP],
                        response_code=telemetry_data[common.Key.RESPONSE_CODE],
                        sensor_data=telemetry_data[common.Key.SENSOR_TELEMETRY],
                    )
                else:
                    self.log.warning(f"Ignoring unparsable data: {data}.")

            except asyncio.CancelledError:
                self.log.debug("read_loop cancelled")
                raise
            except asyncio.TimeoutError:
                self.num_consecutive_read_timeouts += 1
                self.log.warning(
                    f"Read timed out. This is timeout #{self.num_consecutive_read_timeouts} "
                    f"of {MAX_ALLOWED_READ_TIMEOUTS} allowed."
                )
                if self.num_consecutive_read_timeouts >= MAX_ALLOWED_READ_TIMEOUTS:
                    self.log.error(
                        f"Encountered at least {MAX_ALLOWED_READ_TIMEOUTS} timeouts. Raising error."
                    )
                    raise
            except RuntimeError as e:
                self.log.error(f"read_loop failed: {e}")
                raise
            except Exception:
                self.log.exception("read_loop failed")
                raise

    async def read(self) -> dict:
        """Read and unmarshal a json-encoded dict.

        This may be a command acknowedgement or telemetry data.

        Time out if reading takes longer than COMMUNICATE_TIMEOUT seconds.

        Returns
        -------
        data : `dict`
            The read data, after json-decoding it.

        Raises
        ------
        RuntimeError
            In case of not being connected.
            In case parsing gthe JSON data fails.
        """
        if not self.connected:
            raise RuntimeError("Not connected.")
        assert self.reader is not None  # make mypy happy

        read_bytes = await asyncio.wait_for(
            self.reader.readuntil(tcpip.TERMINATOR),
            timeout=COMMUNICATE_TIMEOUT,
        )
        try:
            data = json.loads(read_bytes.decode())
        except json.decoder.JSONDecodeError as e:
            raise RuntimeError(f"Could not parse {read_bytes!r} as json.") from e
        if not isinstance(data, dict):
            raise RuntimeError(
                f"Could not parse {read_bytes!r} as a json-encoded dict."
            )
        return data

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
        json_str = json.dumps({"command": command, "parameters": parameters})
        await asyncio.wait_for(
            self._basic_run_command(json_str), timeout=COMMUNICATE_TIMEOUT
        )

    async def _basic_run_command(self, json_str: str) -> None:
        """Write a json-encoded command dict. Potentially wait forever.

        Parameters
        ----------
        json_str : `str`
            json-encoded dict to write. The dict should be of the form::

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
            assert self.writer is not None  # make mypy happy

            self.writer.write(json_str.encode() + tcpip.TERMINATOR)
            await self.writer.drain()
            while True:
                if not self.connected:
                    raise ConnectionError(
                        "Disconnected while waiting for command response"
                    )
                data = await self.read()
                if common.Key.RESPONSE in data:
                    response = data[common.Key.RESPONSE]
                    if response == common.ResponseCode.OK:
                        return
                    else:
                        raise RuntimeError(f"Command {json_str!r} failed: {response!r}")
                else:
                    self.log.debug("Ignoring non-command-ack")

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
        device_configuration = self.device_configurations.get(sensor_name)
        if device_configuration is None:
            raise RuntimeError(f"No device configuration for sensor_name={sensor_name}")
        if response_code == common.ResponseCode.OK:
            telemetry_method = self.telemetry_dispatch_dict.get(
                device_configuration.sens_type
            )
            if telemetry_method is None:
                raise RuntimeError(
                    f"Unsupported sensor type {device_configuration.sens_type}"
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
                f"Ignoring telemetry for sensor {sensor_name} with unknown response code {response_code}"
            )