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

__all__ = ["MockTemperatureSensor"]

import logging
import random
import time

from lsst.ts.ess.sel_temperature_reader import DELIMITER


class MockTemperatureSensor:
    """Mock Temperature Sensor.

    Parameters
    ----------
    name: `str`
        The name of the sensor.
    channels: `int`
        The number of temperature channels.
    count_offset: `int`
        The offset from where to start counting the channels. Old-style sensors
        start counting at 1 and new style sensors at 0, but this mock class is
        more generic and will accept any number.
    disconnected_channel: `int`, optional
        The channels number for which this class will mock a disconnection.
    log: `logger`' optional
        The logger for which to create a child logger, or None in which case a
        new logger gets requested.
    """

    # Minimum and maximum temperatures (deg_C) for creating random sensor data.
    MIN_TEMP = 18.0
    MAX_TEMP = 30.0

    # The value emitted by a disconnected channel
    DISCONNECTED_VALUE = "9999.9990"

    def __init__(
        self,
        name: str,
        channels: int,
        count_offset: int = 0,
        disconnected_channel: int = None,
        log: logging.Logger = None,
    ) -> None:
        self.name = name
        self.channels = channels
        self.count_offset = count_offset
        self.disconnected_channel = disconnected_channel

        if log is None:
            self.log = logging.getLogger(type(self).__name__)
        else:
            self.log = log.getChild(type(self).__name__)

        self.log.info("__init__")

    async def open(self) -> None:
        pass

    async def close(self) -> None:
        pass

    def format_temperature(self, i: int):
        """Creates a formatted string representing a temperature for the given
        channel.

        Parameters
        ----------
        i: `int`
            The temperature channel.

        Returns
        -------
        s: `str`
            A string representing a temperature.

        """
        temp = random.uniform(
            MockTemperatureSensor.MIN_TEMP, MockTemperatureSensor.MAX_TEMP
        )
        if i == self.disconnected_channel:
            return f"C{i + self.count_offset:02d}={MockTemperatureSensor.DISCONNECTED_VALUE}"
        return f"C{i + self.count_offset:02d}={temp:09.4f}"

    def readline(self):
        """Creates a temperature readout response. The name of this function
        does not reflect what it does. But this is the name of the functions
        in the code that reads the real sensor data so I need to stick with it.

        Returns
        -------
        name, error, resp : `tuple`
        name : `str`
            The name of the device.
        error : `str`
            Error string.
            'OK' = No error
            'Non-ASCII data in response.'
            'Timed out with incomplete response.'
        resp : `str`
            Response read from the mock device.
            Includes terminator string.

        """
        self.log.info("read")
        time.sleep(1)
        err: str = "OK"
        channel_strs = [self.format_temperature(i) for i in range(0, self.channels)]
        resp = DELIMITER.join(channel_strs) + self.terminator
        return self.name, err, resp
