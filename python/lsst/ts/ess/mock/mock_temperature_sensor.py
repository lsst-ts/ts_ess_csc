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

__all__ = ["MockTemperatureSensor", "MIN_TEMP", "MAX_TEMP"]

import logging
import random
import time

import numpy as np

from lsst.ts.ess.sel_temperature_reader import DELIMITER

MIN_TEMP = 18.0
MAX_TEMP = 22.0


class MockTemperatureSensor:
    """Mock Temperature Sensor."""

    def __init__(self, name: str, channels: int):
        self.name = name
        self.channels = channels

        # Device parameters
        self.line_size = None
        self.terminator = None
        self.baudrate = None
        self.read_timeout = None

        self.log = logging.getLogger(__name__)
        self.log.info("__init__")

    def open(self) -> None:
        pass

    def close(self) -> None:
        pass

    def format_temperature(self, i):
        temp = random.uniform(MIN_TEMP, MAX_TEMP)
        s = f"C{i:02d}={temp:09.4f}"
        if i == self.channels - 1:
            s += self.terminator
        else:
            s += DELIMITER
        return s

    def readline(self):
        self.log.info("read")
        err: str = "OK"
        resp = ""
        for i in range(0, self.channels):
            resp += self.format_temperature(i)
        return err, resp
