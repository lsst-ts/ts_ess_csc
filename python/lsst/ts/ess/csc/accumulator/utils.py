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

__all__ = ["get_median_and_std_dev"]

from typing import Tuple

import numpy as np

_QUANTILE = [0.25, 0.5, 0.75]
_STD_DEV_FACTOR = 0.741


def get_median_and_std_dev(
    data: np.ndarray, axis: int | None = None
) -> Tuple[float, float]:
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
