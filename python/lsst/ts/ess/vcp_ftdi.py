# This file is part of ts_ess.
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

"""Implementation of VCP for FTDI USB to serial communication devices.

USB Virtual Communications Port (VCP) class for FTDI USB to serial devices.
This is a minimal implementation, providing methods to open a FTDI USB to
serial device using its serial number and read lines of ASCII strings from
a connected serial device.
"""

__all__ = "VcpFtdi"

import asyncio
import logging
import time
from typing import Any, Dict
from threading import RLock

import pylibftdi
from pylibftdi import Device


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
        Default is 1.0 seconds.
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

    def __init__(self, name: str, device_id: str, log=None):
        if log is None:
            self.log = logging.getLogger(type(self).__name__)
        else:
            self.log = log.getChild(type(self).__name__)
        if name not in VcpFtdi._instances:
            if device_id not in VcpFtdi._devices:
                self.name: str = name
                self._lock: RLock = RLock()
                self._device_id: str = device_id
                self._read_timeout = 1.0
                self._terminator: str = "\r\n"
                self._line_size: int = 0
                self._vcp = Device(
                    device_id,
                    mode="t",
                    encoding="ASCII",
                    lazy_open=True,
                    auto_detach=False,
                )
                VcpFtdi._instances[name] = self
                VcpFtdi._devices[device_id] = self
                self.log.debug(
                    "VcpFtdi:{}: First instantiation "
                    'using device SN "{}".'.format(name, device_id)
                )
            else:
                self.log.debug(
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
            self.log.debug(
                "VcpFtdi: Error: "
                'Attempted multiple instantiation of "{}".'.format(name)
            )
            raise IndexError(
                "VcpFtdi: Error: "
                'Attempted multiple instantiation of "{}".'.format(name)
            )

    @property
    def baudrate(self) -> int:
        """BAUD of the serial device ('int')."""
        baud: int = self._vcp.baudrate
        self._message("Device BAUD rate read: {}.".format(baud))
        return baud

    @baudrate.setter
    def baudrate(self, baud: int) -> None:
        self._vcp.baudrate = baud
        self._message("Device BAUD rate set: {}.".format(baud))

    @property
    def line_size(self) -> int:
        """Serial data line size ('int')."""
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
        """Read timeout of serial data line in seconds ('float')."""
        timeout = self._read_timeout
        self._message("Device read timeout read: {} seconds.".format(timeout))
        return timeout

    @read_timeout.setter
    def read_timeout(self, timeout: float) -> None:
        self._read_timeout = timeout
        self._message("Device read timeout set: {} seconds.".format(timeout))

    @property
    def terminator(self) -> str:
        """Serial data line terminator string ('str')."""
        self._message(
            "Serial data line terminator string read: {}.".format(self._terminator)
        )
        return self._terminator

    @terminator.setter
    def terminator(self, terminator: str) -> None:
        self._terminator = terminator
        self._message("Serial data line terminator string set.")

    def _message(self, text: Any) -> None:
        # Print a message prefaced with the VCP_FTDI object info ('Any').
        self.log.debug(f"VcpFtdi:{self.name}: {text}")

    async def open(self) -> None:
        """Open VCP.

        Opens the virtual communications port, sets BAUD and flushes the device
        input and output buffers.

        Raises
        ------
        IOError if virtual communications port fails to open.
        """
        with self._lock:
            self._vcp.open()
            if not self._vcp.closed:
                self._message("VCP open.")
                self._vcp.flush()
            else:
                self._message("Failed to open VCP.")
                raise IOError(f"VcpFtdi:{self.name}: Failed to open VCP.")

    async def close(self) -> None:
        """Close VCP.

        Raises
        ------
        IOError if virtual communications port fails to close.
        """
        with self._lock:
            self._vcp.close()
            if self._vcp.closed:
                self._message("VCP closed.")
            else:
                self._message("VCP failed to close.")
                raise IOError(f"VcpFtdi:{self.name}: Failed to close VCP.")

    def readline(self) -> str:
        r"""Read a line of ASCII string data from the VCP.

        Returns
        -------
        name, error, resp : 'tuple'
        name: 'str'
            The name of the device
        error : 'str'
            Error string.
            'OK' = No error
            'Non-ASCII data in response.'
            'Timed out with incomplete response.'
        resp : 'str'
            Response read from the VCP.
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
        Optionally implements line size, returning when line_size is met if a
        terminator string is empty.
        """
        err = "OK"
        resp: str = ""
        with self._lock:
            while not resp.endswith("\r\n"):
                try:
                    resp += self._vcp.read(1)
                except pylibftdi.FtdiError as e:
                    err = "FTDI error."
                    raise RuntimeWarning(e)
                if (
                    len(self._terminator) > 0
                    and resp[-len(self._terminator) :] == self._terminator
                ):
                    return self.name, err, resp
                elif 0 < self._line_size <= len(resp):
                    return self.name, err, resp
