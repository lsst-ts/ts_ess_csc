# This file is part of lsst-ts.eas-rpi.
#
# Developed for the LSST Data Management System.
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

"""Abstract class for ESS Instrument serial protocol converter.
"""

__all__ = ('SerialReader')

from abc import ABC, abstractmethod


class SerialReader(ABC):
    """Serial reader for ESS instrument base class.

    Implementations will manage connection to the ESS instrument, provide
    protocol conversion of received instrument output data and provide
    resultant data in list form as follows:
        [timestamp, status, data1, data2, data3, data4 ..... ].
    """

    @abstractmethod
    def __init__(self):
        """Initialize and connect to the ESS instrument.

        Implementations should add any connection parameters here.
        """
        pass

    @abstractmethod
    def read(self):
        """Read ESS instrument.

        Read ESS instrument, test data and populate output data list.
        """
        pass
