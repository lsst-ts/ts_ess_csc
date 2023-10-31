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

__all__ = [
    "Young32400RawDataGenerator",
    "Young32400WeatherStationDataClient",
    "MockYoung32400DataServer",
]

import asyncio
import collections.abc
import dataclasses
import itertools
import logging
import math
import re
import types
from typing import Any

import astropy.units as u
import numpy as np
import numpy.random
import yaml
from astropy.coordinates import Angle
from lsst.ts import salobj, tcpip
from lsst.ts.ess import common
from lsst.ts.ess.common.sensor import compute_dew_point_magnus
from lsst.ts.utils import current_tai, make_done_future

from ..accumulator import AirFlowAccumulator

# Maximum reported rain tip count before the value wraps around.
MAX_RAIN_TIP_COUNT = 9999

# The number of seconds in an hour.
SECONDS_PER_HOUR = 60 * 60

# Format of raw data. The fields are as follows:
#
# * wind_speed: raw counts; scale is sensor-specific
# * wind_direction: relative angle in 10ths of a degree
# * temperature: 0-4000 = 0-1V
# * humidity: 0-4000 = 0-1V = 0-100% humidity
# * pressure: 0-5000 = 0-1V; scale and offset are configurable in the sensor
# * rain: 0-9999 (=MAX_RAIN_TIP_COUNT) tipping bucket tip count
DATA_REGEX = re.compile(
    r"(. )?(?P<wind_speed>\d\d\d\d) "
    r"(?P<wind_direction>\d\d\d\d) "
    r"(?P<temperature>\d\d\d\d) "
    r"(?P<humidity>\d\d\d\d) "
    r"(?P<pressure>\d\d\d\d) "
    r"(?P<rain_tip_count>\d\d\d\d)"
)


class FloatAccumulator:
    """Accumulate values for a particular measurement.

    Parameters
    ----------
    num_samples : `int`
        Number of samples to accumulate. Must be positive.
    """

    def __init__(self, num_samples: int) -> None:
        if num_samples < 1:
            raise ValueError(f"{num_samples=} must be >= 1")
        self.num_samples = num_samples
        self.values: list[float] = []

    def add_sample(self, value: float) -> float | None:
        """Add a value. Return the median, if enough samples have been
        accumulated, else None.

        Parameters
        ----------
        value : `float`
            Raw value to scale and to accumulate.

        Returns
        -------
        median : `float` | `None`
            The median scaled value, if enough samples have been accumulated
            (in which case the accumulator is reset) else None.
        """
        self.values.append(value)
        if len(self.values) >= self.num_samples:
            # The explicit cast to float is needed by mypy
            median = float(np.median(self.values))
            self.clear()
            return median
        return None

    def clear(self) -> None:
        """Clear the accumulator."""
        self.values = []


def float_to_intstr(value: float, max_int: int) -> str:
    """Return a float value converted to an string representation
    of an integer with 4 chars and leading zeros.

    Parameters
    ----------
    value : `float`
        The value to convert.
    max_int : `int`
        The maximum integer value. Must be > 0 and <= 9999.

    Raises
    ------
    ValueError
        If max_int <= 0 or > 9999.
    """
    if not 0 < max_int <= 9999:
        raise ValueError(f"{max_int=} not >0 and <= 9999")
    int_val = int(round(value))
    truncated_int_val = max(0, min(int_val, max_int))
    return f"{truncated_int_val:04d}"


def scaled_from_raw(raw: float, scale: float, offset: float) -> float:
    """Convert raw data to scaled: return raw * scale + offset."""
    return raw * scale + offset


class Young32400WeatherStationDataClient(common.BaseReadLoopDataClient):
    """Get environmental data from Young 32400 weather station
    serial interface.

    The interface is assumed to be connected to a serial-to-ethernet adapter.

    Parameters
    ----------
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

    Notes
    -----
    This code assumes the 32400 is configured to provide ASCII or
    PRECIPITATION formatted output, depending if there is a rain gauge.

    Sensors must be connected as follows (this is the standard order
    for NMEA output, plus the standard input for a rain gauge):

    * VIN1: temperature
    * VIN2: relative humidity
    * VIN3: barometric pressure
    * VIN4: tipping bucket rain gauge
    """

    def __init__(
        self,
        config: types.SimpleNamespace,
        topics: salobj.Controller | types.SimpleNamespace,
        log: logging.Logger,
        simulation_mode: int = 0,
    ) -> None:
        if config.rain_stopped_interval <= config.read_timeout:
            raise ValueError(
                f"{config.rain_stopped_interval=} must be > {config.read_timeout=}"
            )
        if config.sensor_name_dew_point and (
            not config.sensor_name_humidity or not config.sensor_name_temperature
        ):
            raise ValueError(
                f"{config.sensor_name_dew_point=} must be blank unless both "
                f"{config.sensor_name_humidity=} and "
                f"{config.sensor_name_temperature=} are specified"
            )

        # The MOXA serial-to-ethernet adapter connected to the Young weather
        # station requires disconnecting and reconnecting again when the
        # connection times out. This is achieved by setting the auto_reconnect
        # constructor argument to True.
        super().__init__(
            config=config,
            topics=topics,
            log=log,
            simulation_mode=simulation_mode,
            auto_reconnect=True,
        )

        self.topics.tel_airFlow.set(
            sensorName=self.config.sensor_name_airflow, location=self.config.location
        )
        self.topics.tel_dewPoint.set(
            sensorName=self.config.sensor_name_dew_point, location=self.config.location
        )
        self.topics.tel_relativeHumidity.set(
            sensorName=self.config.sensor_name_humidity, location=self.config.location
        )
        num_pressures = len(self.topics.tel_pressure.DataType().pressureItem)
        self.topics.tel_pressure.set(
            sensorName=self.config.sensor_name_pressure,
            location=self.config.location,
            pressureItem=[math.nan] * num_pressures,
            numChannels=1,
        )
        self.topics.tel_rainRate.set(
            sensorName=self.config.sensor_name_rain,
            location=self.config.location,
        )
        num_temperatures = len(self.topics.tel_temperature.DataType().temperatureItem)
        self.topics.tel_temperature.set(
            sensorName=self.config.sensor_name_temperature,
            location=self.config.location,
            temperatureItem=[math.nan] * num_temperatures,
            numChannels=1,
        )

        self.air_flow_accumulator = AirFlowAccumulator(
            log=self.log, num_samples=self.config.num_samples_airflow
        )

        self.humidity_accumulator = FloatAccumulator(
            num_samples=self.config.num_samples_temperature
        )
        self.pressure_accumulator = FloatAccumulator(
            num_samples=self.config.num_samples_temperature
        )
        self.temperature_accumulator = FloatAccumulator(
            num_samples=self.config.num_samples_temperature
        )

        self.mock_data_server: MockYoung32400DataServer | None = None

        # Interval betweens raw data reads (sec) in simulation mode.
        # This should equal the actual rate of the weather station
        # if you want to publish telemetry at the standard rate.
        self.simulation_interval = 0.5

        # Raw data to use in simulation mode.
        # By default the data is cycled (endlessly repeated).
        # But the rain counter cannot easily cycle (other than
        # to wrap around at 9999), so the default is "no rain".
        wstats = Young32400RawDataGenerator(
            mean_rain_rate=0, std_rain_rate=0, read_interval=self.simulation_interval
        )
        self.simulated_raw_data: collections.abc.Iterable[str] = itertools.cycle(
            wstats.create_raw_data_list(config=self.config, num_items=100)
        )

        # Most recent new value of rain tip counter,
        # and the time it was recorded (0 until a change is seen).
        self.last_rain_tip_count = 0
        self.last_rain_tip_timestamp = 0

        # Has a rain tip transition been seen?
        self.rain_tip_transition_seen = False

        self.client: tcpip.Client | None = None

        self.rain_stopped_timer_task = make_done_future()

        # For mocking timeouts, set this to True.
        self.do_timeout = False

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        return yaml.safe_load(
            """
$schema: http://json-schema.org/draft-07/schema#
description: Schema for Young32400WeatherStationDataClient.
type: object
properties:
  host:
    description: IP address of the TCP/IP interface.
    type: string
    format: hostname
  port:
    description: Port number of the TCP/IP interface.
    type: integer
    default: 4001
  connect_timeout:
    description: Timeout for connecting to the weather station (sec).
    type: number
  read_timeout:
    description: >-
      Timeout for reading data from the weather station (sec). Note that the standard
      output rate is either 2 Hz or 15 Hz, depending on configuration.
    type: number
  max_read_timeouts:
    description: Maximum number of read timeouts before an exception is raised.
    type: integer
    default: 5
  num_samples_airflow:
    description: ->
      The number of airflow readings to accumulate before computing statistics
      and reporting the result.
    type: integer
    minimum: 3
  num_samples_temperature:
    description: ->
      The number of temperature, humidity and pressure readings to accumulate
      before computing statistics and reporting the result.
    type: integer
    minimum: 3
  rain_stopped_interval:
    description: ->
      Time (seconds) wait after the rain tip counter value changes
      before reporting that it has stopped raining.
      This must be longer than read_timeout, or the config will be rejected
      (to avoid falsely reporting that the rain has stopped
      if data stops arriving from the weather station).
      For a standard tipping rain gauge with capacity 0.1 mm, this should be
      at least 160 seconds, in order to avoid reporting that it has stopped
      raining while raining lightly (2.4 mm/hr).
    type: number
    default: 160
  sensor_name_airflow:
    description: Wind speed and direction sensor model. Blank if no sensor.
    type: string
  sensor_name_dew_point:
    description: >-
      Sensor name to report for dewPoint. This value is computed from
      relative humidity and temperature; leave blank if you do not want it
      reported (e.g. if either of those sensors is not available).
  sensor_name_humidity:
    description: Humidity sensor model. Blank if no sensor.
    type: string
  sensor_name_pressure:
    description: Atmospheric pressure sensor model. Blank if no sensor.
    type: string
  sensor_name_rain:
    description:  Rain sensor model; probably 52202 or similar. Blank if no sensor.
    type: string
  sensor_name_temperature:
    description: Temperature sensor model. Blank if no sensor.
    type: string
  scale_offset_humidity:
    description: >-
      Humidity % = raw * scale + offset.
      0-4000 raw = 0-1V and this is typically mapped to 0-100% humidity,
      in which case specify [0.025, 0].
    type: array
    items:
      type: number
    minItems: 2
    maxItems: 2
  scale_offset_pressure:
    description: >-
      Barometric pressure in Pa = raw * scale + offset.
      0-4000 raw = 0-5V (sic), and the mapping to pressure is configured in the sensor.
      The default configuration for model 61402V is mbar = 0.12 * mv + 500,
      in which case specify [48, 500] (since 1 mbar = 100 Pa).
    type: array
    items:
      type: number
    minItems: 2
    maxItems: 2
  scale_offset_temperature:
    description: >-
      Temperature in C = (raw * scale) + offset.
      0-4000 raw = 0-1V. Model 41382VC outputs -50 - 50C over this range,
      in which case specify [0.025, -50].
    type: array
    items:
      type: number
    minItems: 2
    maxItems: 2
  scale_offset_wind_direction:
    description:
      Wind direction in deg = (raw * scale) + offset.
      The Young wind sensors all output 0-3600 raw for 0-360 degrees,
      so you probably want scale = 0.1 (or -0.1 if the sign convention
      differs from ours). Offset depends on how the sensor is mounted,
      but we it should typically be nearly 0. So something like [0.1, 0].
    type: array
    items:
      type: number
    minItems: 2
    maxItems: 2
  scale_offset_wind_speed:
    description: >-
      Wind speed in m/s = raw * scale + offset.
      Scale and offset depend on the sensor model; the 32400 Serial Interface
      manual has a Wind Sensor table on page 4 showing values for each model.
      Note that only one model, a cup anenometer, has a non-zero offset.
      For model 05108 specify [0.0834, 0].
    type: array
    items:
      type: number
    minItems: 2
    maxItems: 2
  scale_rain_rate:
    description: >-
        Scale of tipping bucket rain gauge: rainfall in mm = scale * number of tips.
        For model 52202 specify 0.1.
    type: number
  location:
    description: Sensor location (used for all telemetry topics).
    type: string
required:
  - host
  - port
  - connect_timeout
  - read_timeout
  - max_read_timeouts
  - num_samples_airflow
  - num_samples_temperature
  - rain_stopped_interval
  - sensor_name_airflow
  - sensor_name_dew_point
  - sensor_name_humidity
  - sensor_name_pressure
  - sensor_name_rain
  - sensor_name_temperature
  - scale_offset_humidity
  - scale_offset_pressure
  - scale_offset_temperature
  - scale_offset_wind_direction
  - scale_offset_wind_speed
  - scale_rain_rate
  - location
additionalProperties: false
"""
        )

    @property
    def connected(self) -> bool:
        return self.client is not None and self.client.connected

    async def connect(self) -> None:
        if self.connected:
            await self.disconnect()

        if self.simulation_mode > 0:
            self.mock_data_server = MockYoung32400DataServer(
                log=self.log,
                simulated_raw_data=self.simulated_raw_data,
                simulation_interval=self.simulation_interval,
                do_timeout=self.do_timeout,
            )
            await self.mock_data_server.start_task
            host = tcpip.LOCALHOST_IPV4
            port = self.mock_data_server.port
        else:
            host = self.config.host
            port = self.config.port

        self.client = tcpip.Client(host=host, port=port, log=self.log)
        await asyncio.wait_for(self.client.start_task, self.config.connect_timeout)

    def descr(self) -> str:
        assert self.client is not None  # keep mypy happy
        return f"host={self.client.host}, port={self.client.port}"

    async def disconnect(self) -> None:
        self.run_task.cancel()
        self.rain_stopped_timer_task.cancel()
        self.last_rain_tip_timestamp = 0
        self.air_flow_accumulator.clear()
        self.humidity_accumulator.clear()
        self.temperature_accumulator.clear()
        self.pressure_accumulator.clear()
        try:
            if self.connected:
                assert self.client is not None  # make mypy happy
                await self.client.close()
        finally:
            self.client = None
        if self.mock_data_server is not None:
            await self.mock_data_server.close()
            self.mock_data_server = None

    async def handle_data(
        self,
        wind_speed: int,
        wind_direction: int,
        humidity: int,
        temperature: int,
        pressure: int,
        rain_tip_count: int,
    ) -> None:
        """Process data.

        Parameters
        ----------
        wind_direction : `int`
            Wind direction (raw units)
        wind_speed : `int`
            Wind speed (raw units)
        humidity : `int`
            Relative humidity (raw units)
        temperature : `int`
            Air temperature (raw units)
        pressure : `int`
            Air pressure (raw units)
        rain_tip_count : `int`
            Rain tip count (raw units)
        """
        timestamp = current_tai()

        if self.config.sensor_name_airflow:
            self.air_flow_accumulator.add_sample(
                timestamp=current_tai(),
                direction=scaled_from_raw(
                    wind_direction, *self.config.scale_offset_wind_direction
                ),
                speed=scaled_from_raw(wind_speed, *self.config.scale_offset_wind_speed),
                isok=True,
            )
            kwargs = self.air_flow_accumulator.get_topic_kwargs()
            if kwargs:
                await self.topics.tel_airFlow.set_write(**kwargs)

        report_humidity = False
        if self.config.sensor_name_humidity:
            raw_median = self.humidity_accumulator.add_sample(humidity)
            if raw_median is not None:
                report_humidity = True
                await self.topics.tel_relativeHumidity.set_write(
                    relativeHumidityItem=scaled_from_raw(
                        raw=raw_median,
                        scale=self.config.scale_offset_humidity[0],
                        offset=self.config.scale_offset_humidity[1],
                    ),
                    timestamp=timestamp,
                )

        if self.config.sensor_name_pressure:
            raw_median = self.pressure_accumulator.add_sample(pressure)
            if raw_median is not None:
                self.topics.tel_pressure.data.pressureItem[0] = scaled_from_raw(
                    raw=raw_median,
                    scale=self.config.scale_offset_pressure[0],
                    offset=self.config.scale_offset_pressure[1],
                )
                await self.topics.tel_pressure.set_write(timestamp=timestamp)

        report_temperature = False
        if self.config.sensor_name_temperature:
            raw_median = self.temperature_accumulator.add_sample(temperature)
            if raw_median is not None:
                report_temperature = True
                self.topics.tel_temperature.data.temperatureItem[0] = scaled_from_raw(
                    raw=raw_median,
                    scale=self.config.scale_offset_temperature[0],
                    offset=self.config.scale_offset_temperature[1],
                )
                await self.topics.tel_temperature.set_write(timestamp=timestamp)

        if self.config.sensor_name_dew_point and (
            report_humidity or report_temperature
        ):
            relative_humidity = (
                self.topics.tel_relativeHumidity.data.relativeHumidityItem
            )
            temperature = self.topics.tel_temperature.data.temperatureItem[0]
            if not math.isnan(relative_humidity) and not math.isnan(temperature):
                dew_point = compute_dew_point_magnus(
                    relative_humidity=relative_humidity, temperature=temperature
                )
                await self.topics.tel_dewPoint.set_write(
                    dewPointItem=dew_point, timestamp=timestamp
                )

        if self.config.sensor_name_rain:
            if self.last_rain_tip_timestamp == 0:
                # Start recording rain data.
                self.last_rain_tip_count = rain_tip_count
                self.last_rain_tip_timestamp = timestamp
            else:
                if rain_tip_count == self.last_rain_tip_count:
                    # No change, nothing to do
                    return

                # Update the saved values, after making local copies.
                last_rain_tip_count = self.last_rain_tip_count
                last_rain_tip_timestamp = self.last_rain_tip_timestamp
                self.last_rain_tip_count = rain_tip_count
                self.last_rain_tip_timestamp = timestamp

                # Report that it is raining and start the rain stopped timer.
                await self.topics.evt_precipitation.set_write(raining=True)
                self.restart_rain_stopped_timer()

                if not self.rain_tip_transition_seen:
                    # We cannot report the rain rate because this is
                    # the first rain tip counter that we have seen.
                    self.rain_tip_transition_seen = True
                    return

                # Report rain rate.
                rain_tip_dcount = rain_tip_count - last_rain_tip_count
                if rain_tip_dcount < 0:
                    rain_tip_dcount += MAX_RAIN_TIP_COUNT
                if rain_tip_dcount != 1:
                    self.log.warning(
                        "Will not report rainRate due to an unexpected jump "
                        "in the rain tip counter: "
                        f"{last_rain_tip_count=}; {rain_tip_count=}. "
                        "The expected difference is 1, or 9999 to 1"
                    )
                    return

                rain_tip_dt = timestamp - last_rain_tip_timestamp
                rain_rate_mm_per_hr = (
                    rain_tip_dcount
                    * self.config.scale_rain_rate
                    * SECONDS_PER_HOUR
                    / rain_tip_dt
                )
                await self.topics.tel_rainRate.set_write(
                    rainRateItem=round(rain_rate_mm_per_hr)
                )

    def restart_rain_stopped_timer(self) -> None:
        """Start or restart the "rain stopped" timer."""
        self.rain_stopped_timer_task.cancel()
        self.rain_stopped_timer_task = asyncio.create_task(self.rain_stopped_timer())

    async def setup_reading(self) -> None:
        # Start the "rain stopped" timer so we can report "no rain"
        # as soon after starting as it is safe to do so.
        self.restart_rain_stopped_timer()

    async def read_data(self) -> None:
        """Read raw data from the weather station.

        The format is as described by DATA_REGEX.
        """
        assert self.client is not None  # make mypy happy
        read_bytes = await asyncio.wait_for(
            self.client.readuntil(tcpip.DEFAULT_TERMINATOR),
            timeout=self.config.read_timeout,
        )
        data = read_bytes.decode().strip()
        if not data:
            return
        match = DATA_REGEX.fullmatch(data)
        if match is None:
            self.log.warning(f"Ignoring {data=}: could not parse the data")
            return
        # Convert raw data values from str to int.
        raw_data_dict = {key: int(value) for key, value in match.groupdict().items()}
        try:
            await self.handle_data(**raw_data_dict)
        except Exception as e:
            self.log.exception(f"Failed to handle {data=}: {e!r}")

    async def rain_stopped_timer(self) -> None:
        """Wait for the configured time, then report that rain has stopped.

        Intended to be run by restart_rain_stopped_timer.
        """
        await asyncio.sleep(self.config.rain_stopped_interval)
        await self.topics.evt_precipitation.set_write(raining=False)


@dataclasses.dataclass
class Young32400RawDataGenerator:
    """Generate simulated raw data for the Young 32400 weather station.

    Default values are fairly arbitrary but vaguely plausible.
    Default wind direction is intentionally close to 360,
    in order to exercise the wrapping code.
    Units are as follows:

    * wind_direction: deg
    * wind_speed: m/s
    * temperature: C
    * humidity: %
    * pressure: Pa
    * rain_rate: mm/hr

    The class property ``stat_names`` is a list of the statistic names,
    in the same order as the associated field in raw data.
    For each statistics name there is a corresponding f"mean_{name}"
    and f"mean_{name}" constructor argument and attribute.
    Almost all raw fields in DATA_REGEX have the same name as the statistic;
    the one exception is "rain_rate", whose raw field is "rain_tip_count".
    """

    mean_wind_direction: float = 359.9
    std_wind_direction: float = 3.6
    mean_wind_speed: float = 12.3
    std_wind_speed: float = 2.3
    mean_temperature: float = 13.4
    std_temperature: float = 2.4
    mean_humidity: float = 14.5
    std_humidity: float = 2.5
    mean_pressure: float = 105000
    std_pressure: float = 10000
    mean_rain_rate: float = 15.6
    std_rain_rate: float = 2.6
    read_interval: float = 0.5  # expected interval between data reads
    start_rain_tip_count: int = 9990  # to test wraparound

    stat_names: collections.abc.Sequence[str] = dataclasses.field(
        default=(
            "wind_speed",
            "wind_direction",
            "temperature",
            "humidity",
            "pressure",
            "rain_rate",
        ),
        init=False,
    )

    max_rain_tip_count: int = dataclasses.field(default=9999, init=False)

    def create_raw_data_list(
        self, config: types.SimpleNamespace, num_items: int, random_seed: int = 47
    ) -> list[str]:
        """Create simulated raw data for all sensors.

        Use a normal distribution, but truncate out-of-range values.

        Parameters
        ----------
        config : `types.SimpleNamespace`
            Configuration for the data client.
        num_items : `int`
            Number of raw strings to create.
        random_seed : `int`
            Random seed.
        """
        rng = numpy.random.default_rng(random_seed)
        float_array_dict = {
            field_name: rng.normal(
                loc=getattr(self, "mean_" + field_name),
                scale=getattr(self, "std_" + field_name),
                size=num_items,
            )
            for field_name in self.stat_names
        }

        # Wrap wind direction into [0, 360)
        wind_direction = float_array_dict["wind_direction"]
        wind_direction = Angle(wind_direction * u.deg).wrap_at(Angle(360 * u.deg)).deg
        float_array_dict["wind_direction"] = wind_direction

        # Create string lists
        str_list_dict: dict[str, list[str]] = dict()
        for field_name, float_array in float_array_dict.items():
            if field_name == "rain_rate":
                # rain_rate is in mm/hr; raw data is counts
                # so scale mm/hr to counts/sample.
                samples_per_hour = SECONDS_PER_HOUR / self.read_interval
                counts_per_mm = 1 / config.scale_rain_rate
                unscaled_float_array = float_array * counts_per_mm / samples_per_hour
                unscaled_float_array = np.cumsum(unscaled_float_array)
                unscaled_float_array += self.start_rain_tip_count
                unscaled_float_array %= self.max_rain_tip_count
            else:
                scale, offset = getattr(config, "scale_offset_" + field_name)
                unscaled_float_array = (float_array - offset) / scale
            max_int = dict(
                wind_direction=3600,
                rain_rate=self.max_rain_tip_count,
            ).get(field_name, 4000)

            str_list_dict[field_name] = [
                float_to_intstr(value=value, max_int=max_int)
                for value in unscaled_float_array
            ]

        return [
            " ".join(str_list[i] for str_list in str_list_dict.values())
            for i in range(num_items)
        ]


class MockYoung32400DataServer(tcpip.OneClientServer):
    """Mock Young 32400 data server.

    Parameters
    ----------
    log : `logging.Logger`
        Logger.
    simulated_raw_data : iterable [`str`]
        Simulated raw data. If the mock server runs out of data
        then it will log a warning and repeat the final value.
    simulation_interval : `float`
        Interval between writes (sec).
    """

    def __init__(
        self,
        log: logging.Logger,
        simulated_raw_data: collections.abc.Iterable[str],
        simulation_interval: float,
        do_timeout: bool = False,
    ) -> None:
        self.simulated_raw_data = simulated_raw_data
        self.simulation_interval = simulation_interval
        super().__init__(
            host=tcpip.LOCALHOST_IPV4,
            port=0,
            log=log,
            connect_callback=self.connect_callback,
        )
        self.write_loop_task = make_done_future()
        self.do_timeout = do_timeout

    async def connect_callback(self, server: tcpip.OneClientServer) -> None:
        self.write_loop_task.cancel()
        if server.connected:
            self.write_loop_task = asyncio.create_task(self.write_loop())

    async def write_loop(self) -> None:
        data: str | None = None
        try:
            if self.do_timeout:
                raise asyncio.TimeoutError
            for data in self.simulated_raw_data:
                if not self.connected:
                    return
                await self.write(data.encode() + tcpip.DEFAULT_TERMINATOR)
                await asyncio.sleep(self.simulation_interval)
            if data is None:
                raise RuntimeError("no simulated data")

            self.log.info(
                "Mock server ran out of simulated data; repeating the final value"
            )
            while self.connected:
                await self.write(data.encode() + tcpip.DEFAULT_TERMINATOR)
                await asyncio.sleep(self.simulation_interval)
        except Exception as e:
            self.log.exception(f"write loop failed: {e!r}")
