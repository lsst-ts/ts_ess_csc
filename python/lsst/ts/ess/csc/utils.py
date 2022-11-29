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

__all__ = ["get_median"]

import numpy as np

QUANTILE = [0.25, 0.5, 0.75]


def get_median(data: np.ndarray, axis: int = None) -> float:
    """Compute the median using quantiles and ignore the other return
    values.

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
    """
    _, median, _ = np.quantile(data, QUANTILE, axis=axis)
    return median
