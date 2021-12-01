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

__all__ = ["RPiModel"]

import asyncio
import json
import logging
import math
from typing import Any, Dict, List, Union

import yaml

from lsst.ts import salobj, tcpip, utils
from lsst.ts.ess import common
from .base_model import BaseModel, register_model_class

# Time limit for connecting to the RPi (seconds)
CONNECT_TIMEOUT = 5

# Time limit for communicating with the RPi (seconds)
# This includes writing a command and reading the response
# and reading telemetry (seconds)
COMMUNICATE_TIMEOUT = 5


class RPiModel(BaseModel):
    """Get environmental data from a Raspberry Pi with custom hat.

    Parameters
    ----------
    config : types.SimpleNamespace
        The configuration, after validation by get_config_schema
        and conversion to a types.SimpleNamespace.
    csc : `salobj.BaseCsc`
        The CSC using this model.
        Used to access telemetry topics and the fault method.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        topics: salobj.Controller,
        log: logging.Logger,
        simulation_mode: int = 0,
    ) -> None:
        self.device_configurations: Dict[str, Any] = dict()
        self.stream_lock = asyncio.Lock()
        self.last_commands: List[str] = []
        self.reader = None
        self.writer = None
        self.read_loop_task = utils.make_done_future()

        # Set this False before calling start,
        # to test failure to connect to the server.
        # Ignored if not simulating.
        self.enable_mock_server = True

        # Array of NaNs used to initialize reported temperatures.
        num_temp = len(topics.tel_temperature.DataType().temperature)
        self.temperature_nans = [math.nan] * num_temp

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

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return yaml.safe_load(
            """
$schema: http://json-schema.org/draft-07/schema#
description: Schema for RPIModel
type: object
properties:
  host:
    description: IP address of the TCP/IP interface.
    type: string
    format: hostname
    default: "127.0.0.1"
  port:
    description: Port number of the TCP/IP interface.
    type: integer
    default: 5000
  devices:
    type: array
    default:
    - name: EssTemperature4Ch
      sensor_type: Temperature
      channels: 4
      device_type: FTDI
      ftdi_id: AL05OBVR
      location: Test
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

    def configure(self, config) -> None:
        """Configure the CSC.

        Also store the device configurations for easier access when receiving
        and processing telemetry.

        Parameters
        ----------
        config : `types.SimpleNamespace`
            The configuration as described by the schema at
            `lsst.ts.ess.csc.CONFIG_SCHEMA`, as a struct-like object.
        """
        self.config = config
        for device in config.devices:
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
                self.config.host = tcpip.LOCAL_HOST
                self.config.port = self.mock_server.port
            else:
                self.log.info(f"{self}.enable_mock_server false; connection will fail")
                self.config.host = tcpip.LOCAL_HOST
                self.config.port = 0

        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(host=self.config.host, port=self.config.port),
            timeout=CONNECT_TIMEOUT,
        )
        configuration = {"devices": self.config.devices}
        await self.run_command(command="configure", configuration=configuration)
        await self.run_command(command="start")

    async def disconnect(self):
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
                    sensor_data = data[common.Key.TELEMETRY]
                    await self.process_telemetry(data=sensor_data)
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

    async def _basic_run_command(self, json_str) -> None:
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

            self.last_commands.append(json_str)
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
        self, data: List[Union[str, int, float]]
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
        sensor_name = data[0]
        timestamp = data[1]
        sensor_data = data[3:]
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
        temperature[: device_configuration.num_channels] = sensor_data
        telemetry["temperature"] = temperature
        self.log.debug(f"Sending telemetry {telemetry}")
        self.topics.tel_temperature.set_put(**telemetry)

    async def process_hx85a_telemetry(self, data: List[Union[str, int, float]]) -> None:
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
        sensor_name = data[0]
        timestamp = data[1]
        device_configuration = self.device_configurations[sensor_name]
        telemetry = {
            "sensorName": sensor_name,
            "timestamp": timestamp,
            "relativeHumidity": data[3],
            "temperature": data[4],
            "dewPoint": data[5],
            "location": device_configuration.location,
        }
        self.topics.tel_hx85a.set_put(**telemetry)

    async def process_hx85ba_telemetry(
        self, data: List[Union[str, int, float]]
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
        sensor_name = data[0]
        timestamp = data[1]
        device_configuration = self.device_configurations[sensor_name]
        telemetry = {
            "sensorName": sensor_name,
            "timestamp": timestamp,
            "relativeHumidity": data[3],
            "temperature": data[4],
            "barometricPressure": data[5],
            "dewPoint": data[6],
            "location": device_configuration.location,
        }
        self.topics.tel_hx85ba.set_put(**telemetry)

    async def process_telemetry(self, data: List[Union[str, int, float]]) -> None:
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
        self.log.debug(f"Processing data {data}")
        sensor_name = data[0]
        response_code = data[2]
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
            await telemetry_method(data)
        elif response_code == common.ResponseCode.DEVICE_READ_ERROR:
            raise RuntimeError(
                f"Error reading sensor {sensor_name}. Please check the hardware."
            )
        else:
            self.log.warning(
                f"Ignoring telemetry {data} with unknown response code {response_code}"
            )


register_model_class(RPiModel)
