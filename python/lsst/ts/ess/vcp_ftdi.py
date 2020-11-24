# This file is part of ts_ess.
#
# Developed for the Vera C. Rubin Observatory Telescope and Site Systems.
# This product includes software developed by the Vera C. Rubin Observatory
# Project (https://www.lsst.org).
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

"""Implementation of VCP for FTDI USB to serial communication devices.

USB Virtual Communications Port (VCP) class for FTDI USB to serial devices.
This is a minimal implementation, providing methods to open a FTDI USB to
serial device using its serial number and read lines of ASCII strings from
a connected serial device.
"""

__all__ = "VcpFtdi"

from typing import Any, Dict
import logging
import time
from pylibftdi import Device

logging.basicConfig(
    # Configure logging used for printing debug messages.
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.DEBUG,
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


class VcpFtdi:
    r"""USB Virtual Communications Port (VCP) for FTDI device.

    Parameters
    ----------
    name : 'str'
        Identifier for the object.
    device_id : 'str'
        FTDI device serial number.
    baud : 'int', optional
        Serial BAUD rate. Defaults to 9600.
    read_timeout : 'float', optional
        Timeout for serial reads in seconds.
        Default is 1.5 seconds.
    terminator : 'str', optional
        Terminator string for serial data lines.
        Default is '\r\n'.
    line_size : 'int', optional
        Line size for serial string lines.
        Default is 0.

    Raises
    ------
    IndexError if attempted multiple use of FTDI device.
    IndexError if attempted multiple use of instance name.
    """

    _instances: Dict[str, "VcpFtdi"] = {}
    _devices: Dict[str, "VcpFtdi"] = {}

    def __init__(
        self,
        name: str,
        device_id: str,
        baud: int = 9600,
        read_timeout: float = 1.5,
        terminator: str = "/r/n",
        line_size: int = 0,
    ):
        if name not in VcpFtdi._instances:
            if device_id not in VcpFtdi._devices:
                logger.debug(
                    "VcpFtdi:{}: First instantiation "
                    'using device SN "{}".'.format(name, device_id)
                )
                self.name: str = name
                self._device_id: str = device_id
                self._baudrate: int = baud
                self._read_timeout: float = read_timeout
                self._terminator: str = terminator
                self._line_size: int = line_size
                self._vcp = Device(
                    device_id,
                    mode="t",
                    encoding="utf-8",
                    lazy_open=True,
                    auto_detach=False,
                )
                self.open()
                VcpFtdi._instances[name] = self
                VcpFtdi._devices[device_id] = self
            else:
                logger.debug(
                    "VcpFtdi:{}: Error: "
                    'Attempted multiple use of FTDI device "{}".'.format(
                        name, device_id
                    )
                )
                raise IndexError(
                    "VcpFtdi:{}: "
                    'Attempted multiple use of FTDI device "{}".'.format(
                        name, device_id
                    )
                )
        else:
            logger.debug(
                "VcpFtdi: Error: "
                'Attempted multiple instantiation of "{}".'.format(name)
            )
            raise IndexError(
                "VcpFtdi: Error: "
                'Attempted multiple instantiation of "{}".'.format(name)
            )

    @property
    def baudrate(self) -> int:
        """BAUD of the serial device ('int').
        """
        self._vcp_baudrate = self._vcp.baudrate
        self._message("Device BAUD rate read: {}.".format(self._baudrate))
        return self._baudrate

    @baudrate.setter
    def baudrate(self, baud: int) -> None:
        self._vcp.baudrate = baud
        self._baudrate = baud
        self._message("Device BAUD rate set: {}.".format(self._baudrate))

    @property
    def line_size(self) -> int:
        """Serial data line size ('int').
        """
        self._message(
            "Serial data line size read: {} characters.".format(self._baudrate)
        )
        return self._line_size

    @line_size.setter
    def line_size(self, line_size: int) -> None:
        self._line_size = line_size
        self._message(
            "Serial data line size set: {} characters.".format(self._line_size)
        )

    @property
    def read_timeout(self) -> float:
        """Read timeout of serial data line in seconds ('float').
        """
        self._read_timeout = self._vcp.timeout
        self._message(
            "Device read timeout read: {} seconds.".format(self._read_timeout)
        )
        return self._read_timeout

    @read_timeout.setter
    def read_timeout(self, timeout: float) -> None:
        self._vcp.timeout = timeout
        self._read_timeout = timeout
        self._message("Device read timeout set: {} seconds.".format(self._read_timeout))

    @property
    def terminator(self) -> str:
        """Serial data line terminator string ('str').
        """
        self._message(
            "Serial data line terminator string read: {}.".format(self._read_timeout)
        )
        return self._terminator

    @terminator.setter
    def terminator(self, terminator: str) -> None:
        self._terminator = terminator
        self._message("Serial data line terminator string set.")

    def _message(self, text: Any) -> None:
        # Print a message prefaced with the VcpFtdi object info ('Any').
        logger.debug("VcpFtdi:{}: {}".format(self.name, text))

    def open(self) -> None:
        """Open VCP.

        Opens the virtual communications port, sets BAUD and flushes the device
        input and output buffers.

        Raises
        ------
        IOError if virtual communications port fails to open.
        """
        self._vcp.open()
        if self._vcp._opened:
            self._message("VCP open.")
            self._vcp.baudrate = self._baudrate
            self._vcp.flush()
        else:
            self._message("Failed to open VCP.")
            raise IOError("VcpFtdi:{}: Failed to open VCP.")

    def close(self) -> None:
        """Close VCP.

        Raises
        ------
        IOError if virtual communications port fails to close.
        """
        self._vcp.close()
        if not self._vcp._opened:
            self._message("VCP closed.")
        else:
            self._message("VCP failed to close.")
            raise IOError("VcpFtdi:{}: Failed to close VCP.")

    def readline(self) -> str:
        r"""Read a line of ASCII string data from the VCP.

        Returns
        -------
        text_line : 'str'
            Includes terminator string if there is one.
            May be returned empty if nothing was received, partial if the
            readline was started during device reception or partial if
            the read was terminated during reception of data due to timeout.

        Notes
        -----
        Reads device incoming buffer one character at a time until any of
        read_timeout, terminator or line_size constraints are met.
        Implements read timeout, returning if read_timeout is exceeded.
        Tests for decode error, enforcing ASCII data only.
        Optionally implements ASCII line terminator string (Commonly '\r\n'),
        returning when terminator string is read.
        Optionally implements line size, returning when line_size is met. It is
        normally not necessary to use line size if a terminator is present, but
        if a terminator is also specified, the line size must be at least equal
        to the expected line size including the size of terminator string.
        """
        text_line: str = ""
        expiry_time = time.perf_counter() + self._read_timeout
        while time.perf_counter() < expiry_time:
            try:
                text_line += self._vcp.read(1)
            except UnicodeDecodeError:
                break
            if (
                len(self._terminator) > 0
                and text_line[-len(self._terminator) :] == self._terminator
            ):
                break
            if self._line_size > 0 and len(text_line) >= self._line_size:
                break
        return text_line
