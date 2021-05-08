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

"""Implementation of Gill Windsonic ultrasonic anemometer.

Read and perform protocol conversion for Gill Windsonic Ultrasonic Anemometer instrument.
The instrument is assumed to use its default message format - "Gill - Polar, Continuous"
as documented in Gill Windsonic Doc No 1405 PS 0019 Issue 28.
Serial data is output by the anemometer once per second with the following format:

    <STX>Q,ddd,sss.ss,M,00,<ETX>checksum<CR><LF>'

where:

    <STX>       ASCII start character.
    'Q'         Unit Identifier ('Q' is default value).
    ddd         Wind direction. Three character, leading zero's integer. 000-359 degrees.
                Wind direction value is empty ('') when wind speed is below 0.05 m/s.
    sss.ss      Wind speed. Six character, floating point, leading zero's. 0 to 60 m/s.
    'M'         Units of speed measurement ('M' is m/s default)
    '00'        Status.
    <ETX>       ASCII end charactor.
    checksum    Exclusive OR of all bytes in the string between <STX> and <ETX> characters.
    <CR><LF>    2-character terminator ('\r\n').
"""

__all__ = ["WindsonicAnemometer", "DELIMITER"]

import asyncio
import logging
import time
from typing import Any, Dict

from .serial_reader import SerialReader

# Instrument serial parameters ....
BAUDRATE: int = 9600
TIMEOUT: float = 1.2
DELIMITER: str = ","
TERMINATOR: str = "\r\n";

DEFAULT_DIRECTION_VAL: float = 999
DEFAULT_SPEED_VAL: float = 9999.9990


class WindsonicAnemometer(SerialReader):
    """Windsonic Anemometer instrument protocol converter object.

    Parameters
    ----------
    name : `str`
        Name of the Windsonic Anemometer instance.
    uart_device : `uart`
        Serial port instance.

    Raises
    ------
    IndexError if attempted multiple use of instance name.
    IndexError if attempted multiple use of serial device instance.
    """

    def __init__(self, name: str, uart_device, log=None):
        super().__init__(name, uart_device, log)
        if log is None:
            self.log = logging.getLogger(type(self).__name__)
        else:
            self.log = log.getChild(type(self).__name__)
        self._instances: Dict[str, "WindsonicAnemometer"] = {}
        self._devices: Dict[str, "WindsonicAnemometer"] = {}

        if name not in self._instances:
            if uart_device not in self._devices:
                self.name: str = name
                self.comport = uart_device
                self.output = []

                self.direction: float = DEFAULT_DIRECTION_VAL
                self.speed: float = DEFAULT_SPEED_VAL

                self._tmp_direction: float = []
                self._tmp_speed: float = []

                self._read_line_size: int = 0
                self._instances[name] = self
                self._devices[uart_device] = self
                self.log.debug(
                    f"WindsonicAnemometer:{name}: First instantiation "
                    f"using serial device {uart_device.name!r}."
                )
            else:
                self.log.debug(
                    f"WindsonicAnemometer:{name}: Error: "
                    f"Attempted multiple use of serial device instance {uart_device!r}."
                )
                raise IndexError(
                    f"WindsonicAnemometer:{name}: "
                    f"Attempted multiple use of serial device instance {uart_device!r}."
                )
        else:
            self.log.debug(
                "WindsonicAnemometer: Error: "
                f"Attempted multiple instantiation of {name!r}."
            )
            raise IndexError(
                "WindsonicAnemometer: Error: "
                f"Attempted multiple instantiation of {name!r}."
            )

    async def start(self):
        """Open the communication port and set connection parameters."""
        await self.comport.open()
        self.comport.baudrate = BAUDRATE
        self.comport.line_size = self._read_line_size
        self.comport.terminator = TERMINATOR
        self.comport.read_timeout = TIMEOUT
    async def stop(self):
        """Close the comport."""

        await self.comport.close()

    async def _message(self, text: Any) -> None:
        # Print a message prefaced with the SEL_TEMPERATURE object info.
        self.log.debug(f"WindsonicAnemometer:{self.name}: {text}")

    async def read(self) -> []:
        """Read anemometer instrument.

        Read the instrument, test and populate data.

        If sensor data does not meet the instrument protocol, the read is
        invalidated.
        The timestamp is updated following conversion of the read line.
        """
        self._tmp_speed = DEFAULT_SPEED_VAL
        self._tmp_direction = DEFAULT_DIRECTION_VAL
        err: str = ""
        ser_line: str = ""
        line: str = ""
        await self._message("Reading line from comport.")

        # Set up loop variable for async calls
        loop = asyncio.get_event_loop()

        err, ser_line = await loop.run_in_executor(None, self.comport.readline)
        await self._message("Done.")
        if err == "OK":
            resp = ser_line.strip(TERMINATOR)
            data = resp.split(DELIMITER)
            if len(data) == 6:
                if (data[0] == "\x02Q"
                and data[3] == "M"
                and data[4] == "00"
                and data[5][0] == "\x03"):
                    csum_test_str = resp[1:-3]
                    csum_val = int(resp[-2:], 16)
                    checksum: int = 0
                    for i in csum_test_str:
                        checksum ^= ord(i)
                    if checksum == csum_val:
                        self.speed = float(data[2])
                        if not data[1] == "":
                            self.direction = float(data[1])
                else:
                    err = "Received incorrect format, device settings or checksum."
            else:
                err == "Received improper number of items."
        else:
            err == "Timeout."

        self.output = []
        self.output.append(time.time())
        self.output.append(err)
        self.output.append(self.direction)
        self.output.append(self.speed)
