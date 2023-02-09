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

__all__ = ["RPiDataClient", "PASCALS_PER_MILLIBAR"]

import logging
import types
from collections.abc import Sequence
from typing import Any, Callable

import numpy as np
import yaml
from lsst.ts import salobj
from lsst.ts.ess import common

from ..accumulator import AirFlowAccumulator, AirTurbulenceAccumulator
from .controller_data_client import ControllerDataClient

PASCALS_PER_MILLIBAR = 100


class RPiDataClient(ControllerDataClient):
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
        topics: salobj.Controller | types.SimpleNamespace,
        log: logging.Logger,
        simulation_mode: int = 0,
    ) -> None:
        # Array of NaNs used to initialize reported temperatures.
        num_temperatures = len(topics.tel_temperature.DataType().temperature)
        self.temperature_nans = [np.nan] * num_temperatures

        # Cache of data maintained by process_windsonic_telemetry.
        # a dict of sensor_name: AirFlowAccumulator.
        self.air_flow_cache: dict[str, AirFlowAccumulator] = dict()

        # Cache of data maintained by process_csat3b_telemetry.
        # a dict of sensor_name: AirTurbulenceAccumulator.
        self.air_turbulence_cache: dict[str, AirTurbulenceAccumulator] = dict()

        super().__init__(
            config=config, topics=topics, log=log, simulation_mode=simulation_mode
        )

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
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
          - CSAT3B
          - HX85A
          - HX85BA
          - Temperature
          - Windsonic
        channels:
          description: Number of channels.
          type: integer
        device_type:
          description: Type of the device.
          type: string
          enum:
          - FTDI
          - Serial
        baud_rate:
          description: Baud rate of the sensor.
          type: integer
          default: 19200
        location:
          description: >-
            The location of the device. In case of a multi-channel device with
            probes that can be far away from the sensor, a comma separated line
            can be used to give the location of each probe. In that case the
            locations should be given in the order of the channels.
          type: string
        num_samples:
          description: >-
            Number of samples per telemetry sample. Only relevant for
            certain kinds of data, such as wind speed and direction.
            Ignored for other kinds of data.
          type: integer
          minimum: 2
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
        - baud_rate
        - location
required:
  - host
  - port
  - devices
additionalProperties: false
"""
        )

    async def process_temperature_telemetry(
        self,
        sensor_name: str,
        timestamp: float,
        response_code: int,
        sensor_data: Sequence[float],
    ) -> None:
        """Process temperature telemetry.

        Parameters
        ----------
        sensor_name : `str`
            The name of the sensor.
        timestamp : `float`
            The timestamp of the data.
        response_code : `int`
            The ResponseCode
        sensor_data : each of type `float`
            A Sequence of float representing the sensor telemetry data.
        """
        device_configuration = self.device_configurations[sensor_name]
        temperature = self.temperature_nans[:]
        isok = response_code == 0
        if isok:
            temperature[: device_configuration.num_channels] = sensor_data  # type: ignore
        await self.topics.tel_temperature.set_write(
            sensorName=sensor_name,
            timestamp=timestamp,
            numChannels=device_configuration.num_channels,
            temperature=temperature,
            location=device_configuration.location,
        )
        await self.topics.evt_sensorStatus.set_write(
            sensorName=sensor_name, sensorStatus=0, serverStatus=response_code
        )

    async def process_hx85a_telemetry(
        self,
        sensor_name: str,
        timestamp: float,
        response_code: int,
        sensor_data: Sequence[float],
    ) -> None:
        """Process HX85A humidity sensor telemetry.

        Parameters
        ----------
        sensor_name : `str`
            The name of the sensor.
        timestamp : `float`
            The timestamp of the data.
        response_code : `int`
            The ResponseCode
        sensor_data : each of type `float`
            A Sequence of floats representing the sensor telemetry data:

            * relative humidity (%)
            * air temperature (C)
            * dew point (C)
        """
        await self.write_humidity_etc(
            sensor_name=sensor_name,
            timestamp=timestamp,
            dew_point=sensor_data[2],
            pressure=None,
            relative_humidity=sensor_data[0],
            temperature=sensor_data[1],
            isok=response_code == 0,
        )
        await self.topics.evt_sensorStatus.set_write(
            sensorName=sensor_name, sensorStatus=0, serverStatus=response_code
        )

    async def process_hx85ba_telemetry(
        self,
        sensor_name: str,
        timestamp: float,
        response_code: int,
        sensor_data: Sequence[float],
    ) -> None:
        """Process HX85BA humidity sensor telemetry.

        Parameters
        ----------
        sensor_name : `str`
            The name of the sensor.
        timestamp : `float`
            The timestamp of the data.
        response_code : `int`
            The ResponseCode
        sensor_data : each of type `float`
            A Sequence of floats representing the sensor telemetry data:

            * relative humidity (%)
            * air temperature (C)
            * air pressure (mbar)
            * dew point (C)
        """
        await self.write_humidity_etc(
            sensor_name=sensor_name,
            timestamp=timestamp,
            dew_point=sensor_data[3],
            pressure=sensor_data[2] * PASCALS_PER_MILLIBAR,
            relative_humidity=sensor_data[0],
            temperature=sensor_data[1],
            isok=response_code == 0,
        )
        await self.topics.evt_sensorStatus.set_write(
            sensorName=sensor_name, sensorStatus=0, serverStatus=response_code
        )

    async def process_csat3b_telemetry(
        self,
        sensor_name: str,
        timestamp: float,
        response_code: int,
        sensor_data: Sequence[float],
    ) -> None:
        """Process CSAT3B 3-D anemometer telemetry.

        Accumulate a specified number of samples before writing
        the telemetry topic.

        Parameters
        ----------
        sensor_name : `str`
            The name of the sensor.
        timestamp : `float`
            The timestamp of the data.
        response_code : `int`
            The ResponseCode.
        sensor_data : each of type `float`
            A Sequence of float representing the sensor telemetry data.
        """
        device_configuration = self.device_configurations[sensor_name]
        if sensor_name not in self.air_turbulence_cache:
            self.air_turbulence_cache[sensor_name] = AirTurbulenceAccumulator(
                log=self.log, num_samples=device_configuration.num_samples
            )
        accumulator = self.air_turbulence_cache[sensor_name]

        accumulator.add_sample(
            timestamp=timestamp,
            speed=sensor_data[0:3],
            sonic_temperature=sensor_data[3],
            isok=sensor_data[4] == 0 and response_code == 0,
        )
        topic_kwargs = accumulator.get_topic_kwargs()
        if not topic_kwargs:
            return

        self.log.debug(
            "Sending the tel_airTurbulence telemetry and evt_sensorStatus event."
        )
        await self.topics.tel_airTurbulence.set_write(
            sensorName=sensor_name,
            location=device_configuration.location,
            **topic_kwargs,
        )
        await self.topics.evt_sensorStatus.set_write(
            sensorName=sensor_name,
            sensorStatus=sensor_data[4],
            serverStatus=response_code,
        )

    async def write_humidity_etc(
        self,
        sensor_name: str,
        timestamp: float,
        dew_point: float | None,
        pressure: float | None,
        relative_humidity: float | None,
        temperature: float | None,
        isok: bool,
    ) -> None:
        """Write relative humidity and related quantities.

        Parameters
        ----------
        sensor_name : `str`
            Sensor name
        timestamp : `float` | `None`
            Time at which the data was measured (TAI, unix seconds)
        dew_point : `float` | `None`
            Dew point (C)
        pressure : `float` | `None`
            Parometric pressure (Pa)
        relative_humidity : `float` | `None`
            Relative humidity (%)
        temperature : `float` | `None`
            Air temperature (C)
        isok : `bool`
            Is the data valid?
        """
        device_configuration = self.device_configurations[sensor_name]
        if dew_point is not None:
            await self.topics.tel_dewPoint.set_write(
                sensorName=sensor_name,
                timestamp=timestamp,
                dewPoint=dew_point if isok else np.nan,
                location=device_configuration.location,
            )
        if pressure is not None:
            nelts = len(self.topics.tel_pressure.DataType().pressure)
            pressure_array = [np.nan] * nelts
            if isok:
                pressure_array[0] = pressure
            await self.topics.tel_pressure.set_write(
                sensorName=sensor_name,
                timestamp=timestamp,
                pressure=pressure_array,
                numChannels=1,
                location=device_configuration.location,
            )
        if relative_humidity is not None:
            await self.topics.tel_relativeHumidity.set_write(
                sensorName=sensor_name,
                timestamp=timestamp,
                relativeHumidity=relative_humidity if isok else np.nan,
                location=device_configuration.location,
            )
        if temperature is not None:
            nelts = len(self.topics.tel_temperature.DataType().temperature)
            temperature_array = [np.nan] * nelts
            if isok:
                temperature_array[0] = temperature
            await self.topics.tel_temperature.set_write(
                sensorName=sensor_name,
                timestamp=timestamp,
                temperature=temperature_array,
                numChannels=1,
                location=device_configuration.location,
            )

    async def process_windsonic_telemetry(
        self,
        sensor_name: str,
        timestamp: float,
        response_code: int,
        sensor_data: Sequence[float | int],
    ) -> None:
        """Process Gill Windsonic sensor telemetry.

        Parameters
        ----------
        sensor_name : `str`
            The name of the sensor.
        timestamp : `float`
            The timestamp of the data.
        response_code : `int`
            The ResponseCode
        sensor_data : each of type `float`
            A Sequence of floats representing the sensor telemetry data:

            * wind speed (m/s)
            * wind direction (deg)
        """
        device_configuration = self.device_configurations[sensor_name]

        if sensor_name not in self.air_flow_cache:
            self.air_flow_cache[sensor_name] = AirFlowAccumulator(
                num_samples=device_configuration.num_samples
            )
        accumulator = self.air_flow_cache[sensor_name]

        # TODO DM-37648: Remove these lines as soon as ts_xml has been updated.
        if np.isnan(sensor_data[1]):
            direction = -1
        else:
            direction = int(sensor_data[1])

        accumulator.add_sample(
            timestamp=timestamp,
            speed=sensor_data[0],
            direction=direction,
            isok=response_code == common.ResponseCode.OK,
        )

        topic_kwargs = accumulator.get_topic_kwargs()
        if not topic_kwargs:
            return

        # TODO DM-37648: Remove these lines and use **topic_kwargs as soon as
        #  ts_xml has been updated.
        assert isinstance(topic_kwargs["direction"], float)
        assert isinstance(topic_kwargs["directionStdDev"], float)
        telemetry = {
            "timestamp": topic_kwargs["timestamp"],
            "direction": int(topic_kwargs["direction"]),
            "directionStdDev": int(topic_kwargs["directionStdDev"]),
            "speed": topic_kwargs["speed"],
            "speedStdDev": topic_kwargs["speedStdDev"],
            "maxSpeed": topic_kwargs["maxSpeed"],
        }

        await self.topics.tel_airFlow.set_write(
            sensorName=sensor_name,
            location=device_configuration.location,
            **telemetry,
        )
        await self.topics.evt_sensorStatus.set_write(
            sensorName=sensor_name, sensorStatus=0, serverStatus=response_code
        )

    def get_telemetry_dispatch_dict(self) -> dict[str, Callable]:
        return {
            common.SensorType.TEMPERATURE: self.process_temperature_telemetry,
            common.SensorType.HX85A: self.process_hx85a_telemetry,
            common.SensorType.HX85BA: self.process_hx85ba_telemetry,
            common.SensorType.CSAT3B: self.process_csat3b_telemetry,
            common.SensorType.WINDSONIC: self.process_windsonic_telemetry,
        }
