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

__all__ = ["get_circular_mean_and_std_dev", "get_median_and_std_dev"]

import cmath
import logging
import math

import numpy as np

_QUANTILE = [0.25, 0.5, 0.75]
_STD_DEV_FACTOR = 0.741


def get_circular_mean_and_std_dev(
    angles: np.ndarray | list[float],
    log: logging.Logger | None = None,
) -> tuple[float, float]:
    """Compute the circular mean and circular standard deviation
    of an array of angles in degrees.

    Parameters
    ----------
    angles : `list` of `float`
        A sequence of angles in degrees.
    log : `logging.Logger`, optional
        Logger for warnings.

    Returns
    -------
    mean : `float`
        The circular mean.
    std_dev : `float`
        The circular standard deviation. This ranges from 0 to math.inf,
        and will be math.nan if it could not be computed.
        Except as a hack for ts_xml 15 it will be -1 instead of nan or inf
        because some direction std dev fields are reported as int.

    Raises
    ------
    ValueError
        If ``angles`` is empty.
    """
    if len(angles) == 0:
        raise ValueError("angles is empty; you must provide at least one value")
    # See https://en.wikipedia.org/wiki/Directional_statistics
    # for information about statistics on direction.
    complex_sum = np.sum(np.exp(1j * np.radians(angles))) / len(angles)
    circular_mean = math.degrees(cmath.phase(complex_sum))
    if circular_mean < 0:
        circular_mean += 360
    try:
        circular_std = math.degrees(math.sqrt(-2 * math.log(abs(complex_sum))))
    except ValueError:
        if log is not None:
            log.warning(
                "Could not compute circular std dev: {complex_sum=!r}; {angles=}"
            )
        circular_std = math.nan
    # For ts_xml the value is cast to int, so nan or inf are illegal.
    # Use -1 as a sentinal value.
    if not math.isfinite(circular_std):
        circular_std = -1
    return (circular_mean, circular_std)


def get_median_and_std_dev(
    data: np.ndarray | list[float] | list[list[float]], axis: int | None = None
) -> tuple[np.ndarray, np.ndarray] | tuple[float, float]:
    """Compute the median and estimated standard deviation using quantiles.

    Parameters
    ----------
    data : `list` of `float`
        The data to compute the median for.
    axis : `int`
        The axis of the data to use.

    Returns
    -------
    median : `float`
        The median.
    std_dev : `float`
        Estimate of the standard deviation.
    """
    q25, median, q75 = np.quantile(data, _QUANTILE, axis=axis)
    std_dev = _STD_DEV_FACTOR * (q75 - q25)
    return median, std_dev
