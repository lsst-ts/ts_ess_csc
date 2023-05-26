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

__all__ = ["AirTurbulenceAccumulator"]

import logging
from collections.abc import Sequence
from typing import Any

import numpy as np

from .utils import get_median_and_std_dev


class AirTurbulenceAccumulator:
    """Accumulate air turbulence data from a 3-d anemometer.

    This supports writing the airTurbulence telemetry topic,
    whose fields are statistics measured on a set of data.

    Parameters
    ----------
    log : `logging.Logger`
        The logger for which to create a child logger.
    num_samples : `int`
        The number of samples to read before producing aggregate data.

    Attributes
    ----------
    num_samples : `int`
        The number of samples to read before producing aggregate data.
    timestamp : list[float]
        List of timestamps (TAI unix seconds)
    speed : list[float]
        List of wind speed in x, y, z (m/s)
    sonic_temperature : list[float]
        List of sonic temperature (deg C)
    num_bad_samples : int
        Number of invalid samples.

    Notes
    -----
    *To Use*

    For each data sample read, call ``add_sample``.
    The call `get_topic_kwargs``. If it returns a non-empty dict, write
    the airTurbulence topic using the returned dict as keyword arguments.

    ``get_topic_kwargs`` also clears the accumulated data,
    so you can repeat this indefinitely. You need not call ``clear``
    yourself.

    *Bad Data*

    Samples with ``isok=False`` are ignored, other than to increment
    the ``num_bad_samples`` counter. In the unlikely event that we accumulate
    ``num_samples`` of bad data before that many good samples,
    ``do_report`` will be true, but ``get_topic_kwargs`` will return ``nan``
    for all statistical values. The point is to publish *something*,
    since this is telemetry and it should be output at semi-regular intervals.
    Note that the accumulated good data will be lost.
    """

    def __init__(self, log: logging.Logger, num_samples: int) -> None:
        if num_samples < 2:
            raise ValueError(f"{num_samples=} must be > 1")
        self.log = log.getChild(type(self).__name__)
        self.num_samples = num_samples
        self.timestamp: list[float] = list()
        self.speed: list[Sequence[float]] = list()
        self.sonic_temperature: list[float] = list()
        self.num_bad_samples = 0

    @property
    def do_report(self) -> bool:
        """Do we have enough data to report good or bad data?"""
        return max(len(self.speed), self.num_bad_samples) >= self.num_samples

    def add_sample(
        self,
        timestamp: float,
        speed: Sequence[float],
        sonic_temperature: float,
        isok: bool,
    ) -> None:
        """Add a sample.

        Parameters
        ----------
        timestamp : `float`
            Time at which data was taken (TAI unix seconds)
        speed : `list[float]`
            Wind speed in x, y, z (m/s)
        sonic_temperature : `float`
            Sonic temperature (deg C)
        isok : `bool`
            Is the data valid?
        """
        if len(speed) != 3:
            raise ValueError(f"{speed=} must have 3 elements")
        if isok:
            self.timestamp.append(timestamp)
            self.speed.append(speed)
            self.sonic_temperature.append(sonic_temperature)
        else:
            self.num_bad_samples += 1

    def clear(self) -> None:
        """Clear the accumulated data.

        Note that get_topic_kwargs automatically calls this,
        so you typically will not have to.
        """
        self.timestamp = list()
        self.speed = list()
        self.sonic_temperature = list()
        self.num_bad_samples = 0

    def get_topic_kwargs(self) -> dict[str, float | list[float] | bool]:
        """Return data for the airTurbulence telemetry topic.

        Returns
        -------
        topic_kwargs : `dict` [`str`, `float`]
            Data for the airTurbulence telemetry topic as a keyword,
            arguments, or an empty dict if there are not enough samples yet.
            A dict with data will have these keys:

            * timestamp
            * speed
            * speedStdDev
            * speedMagnitude
            * speedMaxMagnitude
            * sonicTemperature
            * sonicTemperatureStdDev
        """
        timestamp = self.timestamp[-1]
        dict_to_return: dict[str, Any] = dict()
        try:
            if len(self.speed) >= self.num_samples:
                # Return good data
                speed_arr = np.column_stack(self.speed)
                speed_median_arr, speed_std_arr = get_median_and_std_dev(
                    data=speed_arr, axis=1
                )
                magnitude_arr = np.linalg.norm(speed_arr, axis=1)
                magnitude_median_arr = np.median(magnitude_arr)
                (
                    sonic_temperature_median,
                    sonic_temperature_std,
                ) = get_median_and_std_dev(self.sonic_temperature)
                dict_to_return = dict(
                    timestamp=timestamp,
                    speed=speed_median_arr,
                    speedStdDev=speed_std_arr,
                    speedMagnitude=magnitude_median_arr,
                    speedMaxMagnitude=np.max(magnitude_arr),
                    sonicTemperature=sonic_temperature_median,
                    sonicTemperatureStdDev=sonic_temperature_std,
                )
                self.clear()
            elif self.num_bad_samples >= self.num_samples:
                # Return bad data
                dict_to_return = dict(
                    timestamp=timestamp,
                    speed=[np.nan] * 3,
                    speedStdDev=[np.nan] * 3,
                    speedMagnitude=np.nan,
                    speedMaxMagnitude=np.nan,
                    sonicTemperature=np.nan,
                    sonicTemperatureStdDev=np.nan,
                )
        except Exception as e:
            self.log.exception(f"Error parsing sensor data: {e!r}")
            raise

        self.log.debug(f"Returning {dict_to_return=!s}")
        return dict_to_return
