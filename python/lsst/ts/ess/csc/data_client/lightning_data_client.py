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

__all__ = ["LightningDataClient"]

import asyncio
import logging
import types
from collections.abc import Sequence
from typing import Any, Callable

import numpy as np
import yaml
from lsst.ts import salobj, utils
from lsst.ts.ess import common

from ..accumulator import ElectricFieldStrengthAccumulator
from .controller_data_client import ControllerDataClient


class LightningDataClient(ControllerDataClient):
    """Get lightning and electrical field strength data from a Raspberry Pi.

    Parameters
    ----------
    config : `types.SimpleNamespace`
        The configuration, after validation by the schema returned
        by `get_config_schema()` and conversion to a types.SimpleNamespace.
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
        super().__init__(
            config=config, topics=topics, log=log, simulation_mode=simulation_mode
        )

        # Timer task to send a event when the electric field strength has
        # dropped below the configurable threshold for a configurable amount of
        # time.
        self.high_electric_field_timer_task = utils.make_done_future()

        # Timer task to send a event when there have been no more lightning
        # strikes for a configurable amount of time.
        self.strike_timer_task = utils.make_done_future()

        # Cache of data maintained by process_efm100c_telemetry.
        # a dict of sensor_name: ElectricFieldStrengthAccumulator.
        self.electric_field_strength_cache: dict[
            str, ElectricFieldStrengthAccumulator
        ] = dict()

    async def sleep_timer(self, sleep_time: float) -> None:
        """Simple timer that sleeps for the given amount of time.

        Parameters
        ----------
        sleep_time : `float`
            The amount of time to sleep [s].
        """
        await asyncio.sleep(sleep_time)

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        return yaml.safe_load(
            """
$schema: http://json-schema.org/draft-07/schema#
description: Schema for LightningDataClient.
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
  max_read_timeouts:
    description: Maximum number of read timeouts before an exception is raised.
    type: integer
    default: 5
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
          - EFM100C
          - LD250
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
          description: Sensor location (used for all telemetry topics).
          type: string
        safe_interval:
          description: >-
            The amount of time [s] after which an event is sent informing that
            no lightning strikes or high electric field have been detected
            anymore.
          type: integer
          default: 10
        num_samples:
          description: >-
            Number of samples per telemetry sample. Only relevant for
            electric field strength data. Ignored for lightning strike data.
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
        - baud_rate
        - safe_interval
        - location
required:
  - host
  - port
  - max_read_timeouts
  - devices
additionalProperties: false
"""
        )

    async def process_efm100c_telemetry(
        self,
        sensor_name: str,
        timestamp: float,
        response_code: int,
        sensor_data: Sequence[float | str | int],
    ) -> None:
        """Process EFM-100C electric field strength detector telemetry.

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

        if sensor_name not in self.electric_field_strength_cache:
            self.electric_field_strength_cache[
                sensor_name
            ] = ElectricFieldStrengthAccumulator(
                num_samples=device_configuration.num_samples
            )
        accumulator = self.electric_field_strength_cache[sensor_name]

        accumulator.add_sample(
            timestamp=timestamp,
            strength=float(sensor_data[0]),
            isok=sensor_data[1] == 0 and response_code == common.ResponseCode.OK,
        )

        topic_kwargs = accumulator.get_topic_kwargs()
        if not topic_kwargs:
            return

        topic_kwargs["location"] = device_configuration.location
        if np.abs(topic_kwargs["strengthMax"]) > device_configuration.threshold:
            if not self.high_electric_field_timer_task.done():
                self.high_electric_field_timer_task.cancel()
            # Then start a new one so the safe time interval is reset.
            self.high_electric_field_timer_task = asyncio.create_task(
                self.sleep_timer(device_configuration.safe_interval)
            )
            self.log.debug("Sending the evt_highElectricField event.")
            await self.topics.evt_highElectricField.set_write(
                sensorName=sensor_name,
                strength=device_configuration.threshold,
            )
        else:
            if self.high_electric_field_timer_task.done():
                self.log.debug("Sending the evt_highElectricField event.")
                await self.topics.evt_highElectricField.set_write(
                    sensorName=sensor_name,
                    strength=np.nan,
                )
        self.log.debug(
            "Sending the tel_electricFieldStrength telemetry and evt_sensorStatus event."
        )
        await self.topics.tel_electricFieldStrength.set_write(
            sensorName=sensor_name,
            **topic_kwargs,
        )
        await self.topics.evt_sensorStatus.set_write(
            sensorName=sensor_name,
            sensorStatus=sensor_data[1],
            serverStatus=response_code,
        )

    async def process_ld250_telemetry(
        self,
        sensor_name: str,
        timestamp: float,
        response_code: int,
        sensor_data: Sequence[float | str | int],
    ) -> None:
        """Process LD-250 lightning detector telemetry.

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
        if sensor_data[0] == common.LD250TelemetryPrefix.STRIKE_PREFIX:
            await self.process_ld250_strike(
                sensor_name=sensor_name,
                timestamp=timestamp,
                response_code=response_code,
                sensor_data=sensor_data,
            )
        elif sensor_data[0] in [
            common.LD250TelemetryPrefix.NOISE_PREFIX,
            common.LD250TelemetryPrefix.STATUS_PREFIX,
        ]:
            await self.process_ld250_noise_or_status(
                sensor_name=sensor_name,
                timestamp=timestamp,
                response_code=response_code,
                sensor_data=sensor_data,
            )
        else:
            self.log.error(f"Received unknown telemetry prefix {sensor_data[0]}.")

        # If the timer task is done, and not canceled, then the safe time
        # interval has passed without any new strikes and a "safe" event can be
        # sent.
        if self.strike_timer_task.done() and not self.strike_timer_task.cancelled():
            await self.topics.evt_lightningStrike.set_write(
                sensorName=sensor_name,
                correctedDistance=np.inf,
                uncorrectedDistance=np.inf,
                bearing=0,
            )

    async def process_ld250_strike(
        self,
        sensor_name: str,
        timestamp: float,
        response_code: int,
        sensor_data: Sequence[float | str | int],
    ) -> None:
        device_configuration = self.device_configurations[sensor_name]
        # First cancel any running timer task.
        if not self.strike_timer_task.done():
            self.strike_timer_task.cancel()
        # Then start a new one so the safe time interval is reset.
        self.strike_timer_task = asyncio.create_task(
            self.sleep_timer(device_configuration.safe_interval)
        )
        await self.topics.evt_lightningStrike.set_write(
            sensorName=sensor_name,
            correctedDistance=float(sensor_data[1]),
            uncorrectedDistance=float(sensor_data[2]),
            bearing=float(sensor_data[3]),
        )

    async def process_ld250_noise_or_status(
        self,
        sensor_name: str,
        timestamp: float,
        response_code: int,
        sensor_data: Sequence[float | str | int],
    ) -> None:
        device_configuration = self.device_configurations[sensor_name]
        isok = response_code == 0
        sensor_status = 0

        close_strike_rate = np.nan
        total_strike_rate = np.nan
        close_alarm_status = False
        severe_alarm_status = False
        heading = np.nan
        if sensor_data[0] == common.LD250TelemetryPrefix.NOISE_PREFIX:
            sensor_status = 1
            isok = False
        if isok:
            close_strike_rate = float(sensor_data[1])
            total_strike_rate = float(sensor_data[2])
            close_alarm_status = sensor_data[3] == 0
            severe_alarm_status = sensor_data[4] == 0
            heading = float(sensor_data[5])

        topic_kwargs = {
            "sensorName": sensor_name,
            "timestamp": timestamp,
            "closeStrikeRate": close_strike_rate,
            "totalStrikeRate": total_strike_rate,
            "closeAlarmStatus": close_alarm_status,
            "severeAlarmStatus": severe_alarm_status,
            "heading": heading,
            "location": device_configuration.location,
        }
        await self.topics.tel_lightningStrikeStatus.set_write(**topic_kwargs)
        await self.topics.evt_sensorStatus.set_write(
            sensorName=sensor_name,
            sensorStatus=sensor_status,
            serverStatus=response_code,
        )

    def get_telemetry_dispatch_dict(self) -> dict[str, Callable]:
        return {
            common.SensorType.EFM100C: self.process_efm100c_telemetry,
            common.SensorType.LD250: self.process_ld250_telemetry,
        }
