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

__all__ = ["AirFlowAccumulator"]

import math

import numpy as np

from .utils import get_circular_mean_and_std_dev, get_median_and_std_dev


# TODO DM-38119: delete this function and stop using it once the data type of
# direction and directionStdDev is float.
def float_as_int(value: float, nan_value: int = -1) -> int:
    """Cast a float value to int, returning nan_value for a NaN."""
    if math.isnan(value):
        return nan_value
    return int(round(value))


class AirFlowAccumulator:
    """Accumulate air flow data from a 2-d anemometer.

    This supports writing the airFlow telemetry topic,
    whose fields are statistics measured on a set of data.

    Parameters
    ----------
    num_samples : `int`
        The number of samples to read before producing aggregate data.

    Attributes
    ----------
    num_samples : `int`
        The number of samples to read before producing aggregate data.
    timestamp : `list` of `float`
        List of timestamps (TAI unix seconds).
    speed : `list` of `float`
        List of wind speed (m/s).
    direction : `list` of `float`
        List of wind direction (deg).
    num_bad_samples : `int`
        Number of invalid samples.

    Raises
    ------
    ValueError
        In case the value of ``num_samples`` is smaller than 2.

    Notes
    -----
    *To Use*

    For each data sample read, call ``add_sample``.
    Then call `get_topic_kwargs``. If it returns a non-empty dict, write the
    airFlow topic using the returned dict as keyword arguments.

    ``get_topic_kwargs`` also clears the accumulated data,
    so you can repeat this indefinitely. You need not call ``clear``
    yourself.

    *Bad Data*

    Samples with ``isok=False`` are ignored, other than to increment
    the ``num_bad_samples`` counter. In the unlikely event that we accumulate
    ``num_samples`` of bad data before that many good samples,
    ``do_report()`` will be true, but ``get_topic_kwargs()`` will return
    ``nan`` for all statistical values. The point is to publish *something*,
    since this is telemetry and it should be output at semi-regular intervals.
    Note that the accumulated good data will be lost.
    """

    def __init__(self, num_samples: int) -> None:
        if num_samples < 2:
            raise ValueError(f"{num_samples=} must be > 1")
        self.num_samples = num_samples
        self.timestamp: list[float] = list()
        self.speed: list[float] = list()
        self.direction: list[float] = list()
        self.num_bad_samples = 0

    @property
    def do_report(self) -> bool:
        """Do we have enough data to report good or bad data?"""
        return max(len(self.speed), self.num_bad_samples) >= self.num_samples

    def add_sample(
        self,
        timestamp: float,
        speed: float,
        direction: float,
        isok: bool,
    ) -> None:
        """Add a sample.

        Parameters
        ----------
        timestamp : `float`
            Time at which data was taken (TAI unix seconds).
        speed : `float`
            Wind speed (m/s).
        direction : `float`
            Wind direction (deg).
        isok : `bool`
            Is the data valid?
        """
        if isok:
            self.timestamp.append(timestamp)
            self.speed.append(speed)
            self.direction.append(direction)
        else:
            self.num_bad_samples += 1

    def clear(self) -> None:
        """Clear the accumulated data.

        Note that ``get_topic_kwargs()`` automatically calls this,
        so you typically will not have to.
        """
        self.timestamp = list()
        self.speed = list()
        self.direction = list()
        self.num_bad_samples = 0

    def get_topic_kwargs(self) -> dict[str, float | list[float] | bool]:
        """Return data for the electricFieldStrength telemetry topic.

        Returns
        -------
        topic_kwargs : `dict` [`str`, `float`]
            Data for the airFlow telemetry topic as a keyword,
            arguments, or an empty dict if there are not enough samples yet.
            A dict with data will have these keys:

            * timestamp
            * direction
            * directionStdDev
            * speed
            * speedStdDev
            * maxSpeed
        """
        timestamp = self.timestamp[-1]
        if len(self.speed) >= self.num_samples:
            direction_arr = np.array(self.direction)
            direction_mean, direction_std = get_circular_mean_and_std_dev(direction_arr)
            speed_arr = np.array(self.speed)
            speed_median, speed_std = get_median_and_std_dev(data=speed_arr)
            self.clear()
            return dict(
                timestamp=timestamp,
                # TODO DM-38119: delete float_as_int once the data type of
                # direction and directionStdDev is float.
                direction=float_as_int(direction_mean),
                directionStdDev=float_as_int(direction_std),
                speed=speed_median,
                speedStdDev=speed_std,
                maxSpeed=np.max(speed_arr),
            )

        if self.num_bad_samples >= self.num_samples:
            # Return bad data
            self.clear()
            return dict(
                timestamp=timestamp,
                direction=-1,
                directionStdDev=-1,
                speed=np.nan,
                speedStdDev=np.nan,
                maxSpeed=np.nan,
            )

        return dict()
