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

__all__ = ["MockAnemometer", "MIN_DIRN", "MAX_DIRN", "MIN_SPEED", "MAX_SPEED", "LOW_WIND_SPEED"]

import asyncio
import logging
import random
import time


MIN_DIRN = 0
MAX_DIRN = 359
MIN_SPEED = 0.0
MAX_SPEED = 60.0
LOW_WIND_SPEED = 0.05

TIMEOUT = 1


class MockAnemometer:
    """Mock Windsonic Anemometer.

    GILL Windsonic Option 1.
    Default format. Polar, Continuous.
    """

    def __init__(
        self, name: str, no_wind: bool, log=None
    ):
        self.name = name

        # Device parameters
        self.line_size = None
        self.baudrate = None
        self.read_timeout = None
        self.no_wind = no_wind

        if log is None:
            self.log = logging.getLogger(type(self).__name__)
        else:
            self.log = log.getChild(type(self).__name__)

        self.log.info("__init__")

    async def open(self) -> None:
        pass

    async def close(self) -> None:
        pass

    def format_anemometer(self):
        if self.no_wind:
            temp_speed: float = random.uniform(MIN_SPEED, LOW_WIND_SPEED - 0.001)
            s = f"Q,,{temp_speed:06.2f},M,00,"
        else:
            temp_speed: float = random.uniform(MIN_SPEED + LOW_WIND_SPEED, MAX_SPEED)
            temp_dirn: int = random.uniform(MIN_DIRN, MAX_DIRN)
            s = f"Q,{temp_dirn:03.0f},{temp_speed:06.2f},M,00,"
        checksum = 0
        for i in s:
            checksum ^= ord(i)
        c = '%0.2X' % checksum
        output = f"\x02{s}\x03{c}\r\n"
        return output

    def readline(self):
        self.log.info("read")
        err: str = "OK"
        resp = ""
        resp += self.format_anemometer()
        return err, resp
