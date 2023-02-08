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

__all__ = ["ElectricFieldStrengthAccumulator"]

import numpy as np

from .utils import get_median_and_std_dev


class ElectricFieldStrengthAccumulator:
    """Accumulate electric field data from a detector.

    This supports writing the electricFieldStrength telemetry topic,
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
    strength : `list` of `float`
        List of electric field strength (kV / m).
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
    electricFieldStrength topic using the returned dict as keyword arguments.

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
        self.strength: list[float] = list()
        self.num_bad_samples = 0

    @property
    def do_report(self) -> bool:
        """Do we have enough data to report good or bad data?"""
        return max(len(self.strength), self.num_bad_samples) >= self.num_samples

    def add_sample(
        self,
        timestamp: float,
        strength: float,
        isok: bool,
    ) -> None:
        """Add a sample.

        Parameters
        ----------
        timestamp : `float`
            Time at which data was taken (TAI unix seconds).
        strength : `float`
            Electric field strength (kV / m).
        isok : `bool`
            Is the data valid?
        """
        if isok:
            self.timestamp.append(timestamp)
            self.strength.append(strength)
        else:
            self.num_bad_samples += 1

    def clear(self) -> None:
        """Clear the accumulated data.

        Note that ``get_topic_kwargs()`` automatically calls this,
        so you typically will not have to.
        """
        self.timestamp = list()
        self.strength = list()
        self.num_bad_samples = 0

    def get_topic_kwargs(self) -> dict[str, float | list[float] | bool]:
        """Return data for the electricFieldStrength telemetry topic.

        Returns
        -------
        topic_kwargs : `dict` [`str`, `float`]
            Data for the electricFieldStrength telemetry topic as a keyword,
            arguments, or an empty dict if there are not enough samples yet.
            A dict with data will have these keys:

            * strength
            * strengthStdDev
            * strengthMax
        """
        if len(self.timestamp) > 0:
            timestamp = self.timestamp[-1]
            if len(self.strength) >= self.num_samples:
                # Return good data
                strength_arr = np.array(self.strength)
                strength_median, strength_std = get_median_and_std_dev(
                    data=strength_arr
                )
                self.clear()
                return dict(
                    timestamp=timestamp,
                    strength=strength_median,
                    strengthStdDev=strength_std,
                    strengthMax=np.max(strength_arr),
                )

            if self.num_bad_samples >= self.num_samples:
                # Return bad data
                self.clear()
                return dict(
                    timestamp=timestamp,
                    strength=np.nan,
                    strengthStdDev=np.nan,
                    strengthMax=np.nan,
                )

        return dict()
