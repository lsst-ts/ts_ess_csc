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
import collections.abc
import contextlib
import logging
import math
import pathlib
import types
import unittest
from typing import TypeAlias

import numpy as np
import pytest
from lsst.ts import salobj, utils
from lsst.ts.ess import common, csc
from lsst.ts.ess.common.sensor import compute_dew_point_magnus

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG
)

PathT: TypeAlias = str | pathlib.Path

# Standard timeout (sec).
STD_TIMEOUT = 5

# Timeout (sec) for creating the controller and remote.
LONG_TIMEOUT = 30


class Young32400DataClientTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        # Prepare for Kafka.
        if hasattr(salobj, "set_random_topic_subname"):
            salobj.set_random_topic_subname()
        else:
            salobj.set_random_lsst_dds_partition_prefix()
        config_schema = csc.Young32400WeatherStationDataClient.get_config_schema()
        self.validator = salobj.DefaultingValidator(config_schema)
        self.index_generator = utils.index_generator()
        default_config_dict = dict(
            host="localhost",
            connect_timeout=5,
            read_timeout=1,
            num_samples_airflow=20,
            num_samples_temperature=20,
            rain_stopped_interval=30,
            sensor_name_airflow="05108",
            sensor_name_dew_point="computed",
            sensor_name_humidity="41382VC",
            sensor_name_pressure="61402V",
            sensor_name_rain="52202H",
            sensor_name_temperature="41382VC",
            scale_offset_humidity=[0.025, 0],
            scale_offset_pressure=[48, 500],
            scale_offset_temperature=[0.025, -50],
            scale_offset_wind_direction=[0.1, 0],
            scale_offset_wind_speed=[0.0834, 0],
            scale_rain_rate=0.1,
            location="WeatherStation",
        )
        default_config_dict = self.validator.validate(default_config_dict)
        self.default_config = types.SimpleNamespace(**default_config_dict)

    @contextlib.asynccontextmanager
    async def create_controller(self) -> collections.abc.AsyncGenerator:
        """Create an ESS Controller and Remote and wait for them to start."""
        index = next(self.index_generator)
        async with salobj.Controller(
            name="ESS", index=index
        ) as self.controller, salobj.Remote(
            domain=self.controller.domain, name="ESS", index=index, readonly=True  # type: ignore
        ) as self.remote:
            yield

    def create_data_client(
        self, config: types.SimpleNamespace
    ) -> csc.Young32400WeatherStationDataClient:
        """Create a Young32400WeatherStationDataClient in simulation mode."""
        validated_config_dict = self.validator.validate(vars(config))
        return csc.Young32400WeatherStationDataClient(
            config=types.SimpleNamespace(**validated_config_dict),
            topics=self.controller,
            log=self.controller.log,
            simulation_mode=True,
        )

    async def test_raw_data_generator(self) -> None:
        field_name_index = {
            field_name: i
            for i, field_name in enumerate(csc.Young32400RawDataGenerator.stat_names)
        }
        config = self.default_config

        # Test some obvious values with zero std deviation
        for field_name, mean, expected_raw in (
            ("wind_direction", 0, "0000"),
            ("wind_direction", 180, "1800"),
            ("wind_direction", 359.9, "3599"),
            ("wind_direction", 360.1, "0001"),
            ("temperature", -50, "0000"),
            ("temperature", 0, "2000"),
            ("temperature", 50, "4000"),
            ("humidity", 0, "0000"),
            ("humidity", 50, "2000"),
            ("humidity", 100, "4000"),
        ):
            data_gen = csc.Young32400RawDataGenerator(
                **{"mean_" + field_name: mean, "std_" + field_name: 0}  # type: ignore
            )
            raw_data = data_gen.create_raw_data_list(config=config, num_items=5)
            field_index = field_name_index[field_name]
            for item in raw_data:
                strings = item.split()
                assert strings[field_index] == expected_raw

        # Test a set of statistics with nonzero std dev.
        num_items = 1000
        data_gen = csc.Young32400RawDataGenerator()
        raw_data = data_gen.create_raw_data_list(config=config, num_items=num_items)
        assert len(raw_data) == num_items
        values = np.array(
            [[float(strval) for strval in item.split()] for item in raw_data],
            dtype=float,
        )
        assert values.shape == (
            num_items,
            len(csc.Young32400RawDataGenerator.stat_names),
        )

        # Compute mean and standard deviation of all raw values.
        # Warning: the values for wind_direction are not trustworthy,
        # due to wraparound and the values for rain_rate are meaningless.
        raw_means = np.mean(values, axis=0)
        raw_stds = np.std(values, axis=0)
        for field_name, field_index in field_name_index.items():
            expected_mean = getattr(data_gen, "mean_" + field_name)
            expected_std = getattr(data_gen, "std_" + field_name)
            if field_name == "rain_rate":
                # The count increments rarely (approx. 20 times over all
                # 1000 samples), so rounding to the nearest int for raw data
                # really messes up the statistics.
                # Just compare the rate derived from final - initial counts
                # to the mean, and be very generous in how close it has to be.
                # We could do better by measuring from the first to the last
                # tip count transition, but this is simpler and good enough.
                tip_counts = values[:, field_index]
                delta_counts = tip_counts[-1] - tip_counts[0]
                if delta_counts < 0:
                    delta_counts += csc.Young32400RawDataGenerator.max_rain_tip_count
                samples_per_hour = 60 * 50 / data_gen.read_interval
                mm_per_count = config.scale_rain_rate
                mean = (delta_counts / num_items) * mm_per_count * samples_per_hour
                print(f"{field_name=}; {mean=:0.2f}; {expected_mean=}; {expected_std=}")
                assert mean == pytest.approx(expected_mean, abs=expected_std * 2)
            elif field_name == "wind_direction":
                # Use circular statistics.
                scale, offset = config.scale_offset_wind_direction
                wind_direction_deg = values[:, field_index] * scale + offset
                mean, std = common.accumulator.get_circular_mean_and_std_dev(
                    wind_direction_deg
                )
                mean_diff = utils.angle_diff(mean, expected_mean).deg
                # Be generous in these comparisons; this is a sanity check
                # that should pass for essentially all random seeds.
                print(
                    f"{field_name=}; {mean=:0.2f}; {expected_mean=}; {std=:0.2f}; {expected_std=}"
                )
                assert mean_diff == pytest.approx(0, abs=expected_std)
                assert std == pytest.approx(expected_std, rel=0.1)
            else:
                # Use standard statistics.
                scale, offset = getattr(config, "scale_offset_" + field_name)
                mean = raw_means[field_index] * scale + offset
                std = raw_stds[field_index] * scale
                # Be generous in these comparisons; this is a sanity check
                # that should pass for essentially all random seeds.
                print(
                    f"{field_name=}; {mean=:0.2f}; {expected_mean=}; {std=:0.2f}; {expected_std=}"
                )
                assert mean == pytest.approx(expected_mean, abs=expected_std)
                assert std == pytest.approx(expected_std, rel=0.1)

    async def test_operation(self) -> None:
        async with self.create_controller():
            config = self.default_config
            config.rain_stopped_interval = 2  # very short
            data_client = self.create_data_client(config)

            # Make the test run quickly
            read_interval = 0.1
            data_client.simulation_interval = read_interval

            # Use an unrealistically large rain rate (50 mm/hr is heavy),
            # so we don't have to wait as long to get rain reported.
            data_gen = csc.Young32400RawDataGenerator(
                read_interval=read_interval,
                mean_rain_rate=360,  # about 1 tip/second
            )
            num_checks_per_topic = 2
            # Need enough items to report rain rate num_checks_per_topic times,
            # plus margin.
            num_items = int(
                (num_checks_per_topic + 1)
                * config.rain_stopped_interval
                / read_interval
            )
            data_client.simulated_raw_data = data_gen.create_raw_data_list(
                config=config, num_items=num_items
            )
            await data_client.start()
            try:
                for i in range(num_checks_per_topic):
                    await self.check_air_flow(config=config, data_gen=data_gen)
                    await self.check_humidity_temperature_pressure_dew_point(
                        config=config, data_gen=data_gen
                    )
                    if i == 0:
                        data = await self.remote.evt_precipitation.next(
                            flush=False, timeout=STD_TIMEOUT
                        )
                        assert data.raining
                    await self.check_rain_rate(config=config, data_gen=data_gen)

                # When the simulator runs out of simulated data,
                # this gives the rain stopped timer a chance to expire.
                data = await self.remote.evt_precipitation.next(
                    flush=False, timeout=STD_TIMEOUT
                )
                assert not data.raining
            finally:
                await data_client.stop()

    async def check_air_flow(
        self, config: types.SimpleNamespace, data_gen: csc.Young32400RawDataGenerator
    ) -> None:
        """Check the next sample of airFlow.

        Parameters
        ----------
        config : `types.SimpleNamespace`
            The configuration of the weather data client.
        data_gen : `csc.Young32400RawDataGenerator`
            The data generator used to generate simulated raw data.
        """
        data = await self.remote.tel_airFlow.next(flush=False, timeout=STD_TIMEOUT)
        self.check_data(
            data,
            sensorName=config.sensor_name_airflow,
            location=config.location,
        )
        direction_diff = utils.angle_diff(
            data.direction, data_gen.mean_wind_direction
        ).deg
        assert direction_diff == pytest.approx(0, abs=data_gen.std_wind_direction)

        # Note: the standard deviation is computed from a small number
        # of samples and direction is cast to int (in ts_xml 15)
        # so it may vary even more from the specified value.
        print(
            f"{data.directionStdDev=:0.2f}; {data_gen.std_wind_direction=}; "
            f"{data.speedStdDev=:0.2f}; {data_gen.std_wind_speed=}"
        )
        assert data.directionStdDev == pytest.approx(data_gen.std_wind_direction, rel=1)
        assert data.speed == pytest.approx(
            data_gen.mean_wind_speed, rel=data_gen.std_wind_speed
        )
        assert data.speedStdDev == pytest.approx(data_gen.std_wind_speed, rel=0.5)

    async def check_humidity_temperature_pressure_dew_point(
        self, config: types.SimpleNamespace, data_gen: csc.Young32400RawDataGenerator
    ) -> None:
        """Check the next sample of relativeHumidity, temperature,
        pressure and dewPoint.

        Parameters
        ----------
        config : `types.SimpleNamespace`
            The configuration of the weather data client.
        data_gen : `csc.Young32400RawDataGenerator`
            The data generator used to generate simulated raw data.
        """
        data = await self.remote.tel_relativeHumidity.next(
            flush=False, timeout=STD_TIMEOUT
        )
        self.check_data(
            data,
            sensorName=config.sensor_name_humidity,
            location=config.location,
        )
        read_humidity = data.relativeHumidityItem
        assert read_humidity == pytest.approx(
            data_gen.mean_humidity, abs=data_gen.std_humidity
        )

        data = await self.remote.tel_temperature.next(flush=False, timeout=STD_TIMEOUT)
        self.check_data(
            data,
            sensorName=config.sensor_name_temperature,
            location=config.location,
            numChannels=1,
        )
        read_temperature = data.temperatureItem[0]
        assert read_temperature == pytest.approx(
            data_gen.mean_temperature, abs=data_gen.std_temperature
        )
        assert all(math.isnan(value) for value in data.temperatureItem[1:])

        data = await self.remote.tel_pressure.next(flush=False, timeout=STD_TIMEOUT)
        self.check_data(
            data,
            sensorName=config.sensor_name_pressure,
            location=config.location,
            numChannels=1,
        )
        assert data.pressureItem[0] == pytest.approx(
            data_gen.mean_pressure, abs=data_gen.std_pressure
        )
        assert all(math.isnan(value) for value in data.pressureItem[1:])

        expected_dew_point = compute_dew_point_magnus(
            relative_humidity=read_humidity,
            temperature=read_temperature,
        )
        data = await self.remote.tel_dewPoint.next(flush=False, timeout=STD_TIMEOUT)
        self.check_data(
            data, sensorName=config.sensor_name_dew_point, location=config.location
        )
        assert data.dewPointItem == pytest.approx(expected_dew_point)

    async def check_rain_rate(
        self, config: types.SimpleNamespace, data_gen: csc.Young32400RawDataGenerator
    ) -> None:
        """Check the next sample of rainRate.

        Parameters
        ----------
        config : `types.SimpleNamespace`
            The configuration of the weather data client.
        data_gen : `csc.Young32400RawDataGenerator`
            The data generator used to generate simulated raw data.
        """
        data = await self.remote.tel_rainRate.next(flush=False, timeout=STD_TIMEOUT)
        self.check_data(
            data,
            sensorName=config.sensor_name_rain,
            location=config.location,
        )
        print(
            f"{data.rainRateItem=}; {data_gen.mean_rain_rate=}; {data_gen.std_rain_rate=}"
        )
        assert data.rainRateItem == pytest.approx(data_gen.mean_rain_rate, rel=0.1)

    def check_data(self, data: salobj.BaseMsgType, **kwargs: str | int) -> None:
        for field_name, expected_value in kwargs.items():
            assert getattr(data, field_name) == expected_value

    async def mock_connect(self) -> None:
        pass

    async def test_read_timeout(self) -> None:
        async with self.create_controller():
            config = self.default_config
            config.rain_stopped_interval = 2  # very short
            data_client = self.create_data_client(config)

            # Make the test run quickly
            read_interval = 0.1
            data_client.simulation_interval = read_interval

            # Use an unrealistically large rain rate (50 mm/hr is heavy),
            # so we don't have to wait as long to get rain reported.
            data_gen = csc.Young32400RawDataGenerator(
                read_interval=read_interval,
                mean_rain_rate=360,  # about 1 tip/second
            )
            num_checks_per_topic = 2
            # Need enough items to report rain rate num_checks_per_topic times,
            # plus margin.
            num_items = int(
                (num_checks_per_topic + 1)
                * config.rain_stopped_interval
                / read_interval
            )
            data_client.simulated_raw_data = data_gen.create_raw_data_list(
                config=config, num_items=num_items
            )
            data_client.do_timeout = True
            assert data_client.num_reconnects == 0
            await data_client.start()
            await asyncio.sleep(1.0)
            assert data_client.num_reconnects == 5
            await data_client.stop()
