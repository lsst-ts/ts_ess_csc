# This file is part of ts_hvac.
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

__all__ = ["mbar_to_pa"]

import astropy.units as u
from astropy.units import misc


def mbar_to_pa(value: float) -> float:
    """Convert a value in millibar to a value in Pa.

    Parameters
    ----------
    value: `float`
        The value in millibar.

    Returns
    -------
    float
        The value in Pa.

    Notes
    -----
    All astropy S.I. units support prefixes like 'milli-'. Since 'bar' is a
    'misc' unit, it doesn't support prefixes. For millibar an exception was
    made and 'mbar' was added. See

    https://github.com/astropy/astropy/pull/7863

    This is not documented in the astropy documentation!
    """
    quantity_in_mbar = value * misc.mbar
    quantity_in_pa = quantity_in_mbar.to(u.Pa)
    return quantity_in_pa.value
