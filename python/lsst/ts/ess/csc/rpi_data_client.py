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

__all__ = ["RPiDataClient"]

import asyncio
import json
import logging
import math
import types
from typing import Any, Dict, Sequence, Union

import yaml

from lsst.ts import salobj, tcpip
from lsst.ts.ess import common

# Time limit for connecting to the RPi (seconds)
CONNECT_TIMEOUT = 5

# Time limit for communicating with the RPi (seconds)
# This includes writing a command and reading the response
# and reading telemetry (seconds)
COMMUNICATE_TIMEOUT = 5


class RPiDataClient(common.BaseDataClient):
    """Get environmental data from a Raspberry Pi with custom hat.

    Parameters
    ----------
    name : str
    config : types.SimpleNamespace
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
        topics: Union[salobj.Controller, types.SimpleNamespace],
        log: logging.Logger,
        simulation_mode: int = 0,
    ) -> None:
        self.device_configurations: Dict[str, Any] = dict()
        self.stream_lock = asyncio.Lock()
        self.reader = None
        self.writer = None

        # Set this False before calling start,
        # to test failure to connect to the server.
        # Ignored if not simulating.
        self.enable_mock_server = True

        # Array of NaNs used to initialize reported temperatures.
        num_temperatures = len(topics.tel_temperature.DataType().temperature)
        self.temperature_nans = [math.nan] * num_temperatures

        # Dict of SensorType: processing method
        self.telemetry_dispatch_dict = {
            common.SensorType.TEMPERATURE: self.process_temperature_telemetry,
            common.SensorType.HX85A: self.process_hx85a_telemetry,
            common.SensorType.HX85BA: self.process_hx85ba_telemetry,
        }

        # Mock server for simulation mode
        self.mock_server = None

        super().__init__(
            config=config, topics=topics, log=log, simulation_mode=simulation_mode
        )
        self.configure()

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return yaml.safe_load(
            """
$schema: http://json-schema.org/draft-07/schema#
description: Schema for RPiDataClient
type: object
properties:
  host:
    description: IP address of the TCP/IP interface.
    type: string
    format: hostname
  port:
    description: Port number of the TCP/IP interface.
    type: integer
    default: 5000
  devices:
    type: array
    minItems: 1
    items:
      type: object
      properties:
        name:
          description: Name of the sensor.
          type: string
        sensor_type:
          description: Type of the sensor.
          type: string
          enum:
          - HX85A
          - HX85BA
          - Temperature
          - Wind
        channels:
          description: Number of channels.
          type: integer
        device_type:
          description: Type of the device.
          type: string
          enum:
          - FTDI
          - Serial
        location:
          description: >-
            The location of the device. In case of a multi-channel device with
            probes that can be far away from the sensor, a comma separated line
            can be used to give the location of each probe. In that case the
            locations should be given in the order of the channels.
          type: string
      anyOf:
      - if:
          properties:
            device_type:
              const: FTDI
        then:
          properties:
            ftdi_id:
              description: FTDI Serial ID to connect to.
              type: string
      - if:
          properties:
            device_type:
              const: Serial
        then:
          properties:
            serial_port:
              description: Serial port to connect to.
              type: string
      required:
        - name
        - sensor_type
        - device_type
        - location
required:
  - host
  - port
  - devices
additionalProperties: false
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
                location=device[common.Key.LOCATION],
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
        await self.run_command(command="start")

    async def disconnect(self) -> None:
        """Disconnect from the RPi.

        Always safe to call, though it may raise asyncio.CancelledError
        if the writer is currently being closed.
        """
        try:
            if self.connected:
                await self.run_command(command="stop")
            if self.connected:
                await self.run_command(command="exit")
        except ConnectionError:
            # The connection was lost.
            # This is not worth getting upset about.
            self.log.debug("Connection lost in disconnect")
        finally:
            if self.connected:
                await asyncio.wait_for(
                    tcpip.close_stream_writer(self.writer), timeout=CONNECT_TIMEOUT
                )
            if self.mock_server is not None:
                await self.mock_server.close()

    async def run(self) -> None:
        """Read and process data from the RPi."""
        try:
            while self.connected:
                async with self.stream_lock:
                    data = await self.read()
                if common.Key.RESPONSE in data:
                    self.log.warning("Read a command response with no command pending")
                elif common.Key.TELEMETRY in data:
                    self.log.debug(f"Processing data {data}")
                    telemetry_data = data[common.Key.TELEMETRY]
                    if len(telemetry_data) <= 4:
                        self.log.warning(
                            f"Ignoring telemetry data with fewer than 4 fields: {telemetry_data}."
                        )
                        continue
                    sensor_name = telemetry_data[0]
                    if not isinstance(sensor_name, str):
                        self.log.warning(
                            f"Ignoring data with non-str sensor_name: {sensor_name!r}."
                        )
                        continue
                    timestamp = telemetry_data[1]
                    if not isinstance(sensor_name, float):
                        self.log.warning(
                            f"Ignoring data with non-float timestamp: {timestamp!r}."
                        )
                        continue
                    response_code = telemetry_data[2]
                    if not isinstance(response_code, int):
                        self.log.warning(
                            f"Ignoring data with non-int response_code: {response_code!r}."
                        )
                        continue
                    sensor_data = telemetry_data[3:]
                    if not all(isinstance(value, float) for value in sensor_data):
                        self.log.warning(
                            f"Ignoring data with non-float sensor_data: {sensor_data!r}."
                        )
                        continue
                    await self.process_telemetry(
                        sensor_name=sensor_name,
                        timestamp=timestamp,
                        response_code=response_code,
                        sensor_data=sensor_data,
                    )
                else:
                    self.log.warning(f"Ignoring unparsable data: {data}.")

            err_msg = "Connection lost."
            self.log.error(err_msg)
            raise ConnectionError("Connection lost")
        except asyncio.CancelledError:
            self.log.debug("read_loop cancelled")
            raise
        except asyncio.TimeoutError:
            self.log.error("Read timed out")
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
        """
        if not self.connected:
            raise RuntimeError("Not connected.")
        assert self.reader is not None  # make mypy happy

        read_bytes = await asyncio.wait_for(
            self.reader.readuntil(tcpip.TERMINATOR), timeout=COMMUNICATE_TIMEOUT
        )
        try:
            data = json.loads(read_bytes.decode())
        except json.decoder.JSONDecodeError as e:
            raise RuntimeError(f"Could not parse {read_bytes} as json.") from e
        if not isinstance(data, dict):
            raise RuntimeError(f"Could not parse {read_bytes} as a json-encoded dict.")
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
            If not connected
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

    async def process_temperature_telemetry(
        self,
        sensor_name: str,
        timestamp: float,
        response_code: int,
        sensor_data: Sequence[float],
    ) -> None:
        """Process the temperature telemetry and send to EFD.

        Parameters
        ----------
        data : `list`
            A list containing the timestamp, error and sensor data. The order
            of the items in the list is:
            - Sensor name : `str`
            - Timestamp : `float`
            - Response code : `int`
            - One or more sensor data : each of type `float`
        """
        device_configuration = self.device_configurations[sensor_name]
        telemetry = {
            "sensorName": sensor_name,
            "timestamp": timestamp,
            "numChannels": device_configuration.num_channels,
            "location": device_configuration.location,
        }

        if len(sensor_data) != device_configuration.num_channels:
            raise RuntimeError(
                f"Expected {device_configuration.num_channels} temperatures "
                f"but received {len(sensor_data)}."
            )
        temperature = self.temperature_nans[:]
        temperature[: device_configuration.num_channels] = sensor_data  # type: ignore
        telemetry["temperature"] = temperature
        self.log.debug(f"Sending telemetry {telemetry}")
        self.topics.tel_temperature.set_put(**telemetry)

    async def process_hx85a_telemetry(
        self,
        sensor_name: str,
        timestamp: float,
        response_code: int,
        sensor_data: Sequence[float],
    ) -> None:
        """Process the HX85A humidity sensor telemetry and send to EFD.

        Parameters
        ----------
        data : `list`
            A list containing the timestamp, error and sensor data. The order
            of the items in the list is:
            - Sensor name : `str`
            - Timestamp : `float`
            - Response code : `int`
            - One or more sensor data : each of type `float`
        """
        device_configuration = self.device_configurations[sensor_name]
        telemetry = {
            "sensorName": sensor_name,
            "timestamp": timestamp,
            "relativeHumidity": sensor_data[0],
            "temperature": sensor_data[1],
            "dewPoint": sensor_data[2],
            "location": device_configuration.location,
        }
        self.topics.tel_hx85a.set_put(**telemetry)

    async def process_hx85ba_telemetry(
        self,
        sensor_name: str,
        timestamp: float,
        response_code: int,
        sensor_data: Sequence[float],
    ) -> None:
        """Process the HX85BA humidity sensor telemetry and send to EFD.

        Parameters
        ----------
        data : `list`
            A list containing the timestamp, error and sensor data. The order
            of the items in the list is:
            - Sensor name : `str`
            - Timestamp : `float`
            - Response code : `int`
            - One or more sensor data : each of type `float`
        """
        device_configuration = self.device_configurations[sensor_name]
        telemetry = {
            "sensorName": sensor_name,
            "timestamp": timestamp,
            "relativeHumidity": sensor_data[0],
            "temperature": sensor_data[1],
            "barometricPressure": sensor_data[2],
            "dewPoint": sensor_data[3],
            "location": device_configuration.location,
        }
        self.topics.tel_hx85ba.set_put(**telemetry)

    async def process_telemetry(
        self,
        sensor_name: str,
        timestamp: float,
        response_code: int,
        sensor_data: Sequence[float],
    ) -> None:
        """Process the sensor telemetry

        Parameters
        ----------
        data : `list`
            A list containing the timestamp, error and sensor data. The order
            of the items in the list is:
            - Sensor name : `str`
            - Timestamp : `float`
            - Response code : `int`
            - One or more sensor data : each of type `float`

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
