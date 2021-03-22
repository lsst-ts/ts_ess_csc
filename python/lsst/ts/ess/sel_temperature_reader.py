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

r"""Implementation of SEL temperature instrument.

Read and perform protocol conversion for Straight Engineering Limited (SEL)
temperature measurement instrument.
SEL temperature instruments output serial data in lines terminated by '\r\n'.
There are multiple SEL temperature instruments with different numbers of
channels. The number of channels must be specified at instantiation.
The format of a 4-channel instruments output line is:

    'C00=snnn.nnnn,C01=snnn.nnnn,C02=snnn.nnnn,C03=snnn.nnnn\r\n'

where:

    'C00='      4-character preamble with Celcius ('C') and
                two digit channel number.

    'snnn.nnnn' 9-character decimal value with negative sign or positive value
                (s = '-' or '0..9') and decimal point in the fifth position.

    ','         Single character delimiter.

    '\r\n'      2-character terminator.
"""

__all__ = ["SelTemperature", "DELIMITER"]

from typing import Any, Dict
import logging
import time
from .serial_reader import SerialReader

# Instrument serial parameters ....
BAUDRATE: int = 19200
"""BAUD for SEL temperature instrument communications ('int').
"""

READ_TIMEOUT: float = 1.5
"""Serial read timeout for SEL temperature instrument communications ('float').

The read timeout is set to allow a guaranteed timeout for the recurring
instrument channel serial reads. The number of channels varies between
SEL instruments (4, 5, 8 etc.). The default read timeout is chosen to
comfortably allow for up to eight channels at 19200 BAUD.
"""

# SEL Temperature Instrument serial data string ....
PREAMBLE_SIZE: int = 4
"""Serial data channel preamble size.
"""

VALUE_SIZE: int = 9
"""Serial data temperature value size.
"""

DELIMITER: str = ","
"""Serial data channel delimiter.
"""

TERMINATOR: str = "\r\n"
"""Serial data line terminator.
"""

DEFAULT_VAL: float = "NaN"
"""Default value for unread or errored temperature channels.
"""

logger = logging.getLogger(__name__)


class SelTemperature(SerialReader):
    """SEL temperature instrument protocol converter object.

    Parameters
    ----------
    name : `str`
        Name of the SelTemperature instance.
    channels : `int`
        Number of temperature instrument channels.
    uart_device : `uart`
        Serial port instance.

    Raises
    ------
    IndexError if attempted multiple use of instance name.
    IndexError if attempted multiple use of serial device instance.
    """

    _instances: Dict[str, "SelTemperature"] = {}
    _devices: Dict[str, "SelTemperature"] = {}

    def __init__(self, name: str, uart_device, channels: int):
        super().__init__(name, uart_device, channels)
        if name not in SelTemperature._instances:
            if uart_device not in SelTemperature._devices:
                self.name: str = name
                self._channels: int = channels
                self.comport = uart_device

                self.temperature: float = []
                self.output = []

                self._preamble_str: str = []
                self._tmp_temperature: float = []
                for i in range(self._channels):
                    self._tmp_temperature.append(DEFAULT_VAL)
                    self.temperature.append(DEFAULT_VAL)
                    self._preamble_str.append(f"C{i:02}=")

                self._read_line_size: int = self._channels * (
                    PREAMBLE_SIZE + VALUE_SIZE + len(DELIMITER)
                ) - (len(DELIMITER)) + (len(TERMINATOR))

                self.comport.open()
                self.comport.line_size = self._read_line_size
                self.comport.terminator = TERMINATOR
                self.comport.baudrate = BAUDRATE
                self.comport.read_timeout = READ_TIMEOUT

                SelTemperature._instances[name] = self
                SelTemperature._devices[uart_device] = self
                logger.debug(
                    "SelTemperature:{}: First instantiation "
                    'using serial device "{}".'.format(name, uart_device.name)
                )
            else:
                logger.debug(
                    "SelTemperature:{}: Error: "
                    'Attempted multiple use of serial device instance "{}".'.format(
                        name, uart_device
                    )
                )
                raise IndexError(
                    "SelTemperature:{}: "
                    'Attempted multiple use of serial device instance "{}".'.format(
                        name, uart_device
                    )
                )
        else:
            logger.debug(
                "SelTemperature: Error: "
                'Attempted multiple instantiation of "{}".'.format(name)
            )
            raise IndexError(
                "SelTemperature: Error: "
                'Attempted multiple instantiation of "{}".'.format(name)
            )

    def _message(self, text: Any) -> None:
        # Print a message prefaced with the SEL_TEMPERATURE object info.
        logger.debug("SelTemperature:{}: {}".format(self.name, text))

    def _test_val(self, preamble, sensor_str):
        """Test temperature channel data string.

        Parameters
        ----------
        preamble : 'str'
            Preamble string for channel data (eg."C01=").
        sensor_str : 'str'
            Sensor channel data string (eg."C01=0001.4500")

        Returns
        -------
        Status : 'bool'
            Return is True if sensor string is valid, False if not.
        """
        if sensor_str[0:PREAMBLE_SIZE] == preamble:
            try:
                float(
                    sensor_str[
                        PREAMBLE_SIZE : PREAMBLE_SIZE + VALUE_SIZE + len(DELIMITER) - 1
                    ]
                )
                return True
            except ValueError as e:
                logger.exception(e)
                return False
                pass

    def read(self) -> []:
        """Read temperature instrument.

        Read SEL instrument, test data and populate temperature channel data.

        The SEL instrument has a fixed line size (Depending upon number
        of channels). The read is invalid if the read line size is incorrect.
        If line size error is found, temperature data is populated with default
        value ('Nan').
        If sensor data (preamble and value) does not meet the instrument
        protocol, the read is invalidated.
        If protocol error is found, temperature data is populated with default
        value ('Nan').
        The timestamp is updated following conversion of the read line.
        The line error flag is updated with True if any error found and False
        if no error.
        """
        for i in range(self._channels):
            self._tmp_temperature[i] = DEFAULT_VAL
        err: str = ""
        ser_line: str = ""
        line: str = ""
        err, ser_line = self.comport.readline()
        if err == "OK":
            if (
                ser_line[-len(TERMINATOR) :] == TERMINATOR
                and len(ser_line) == self._read_line_size
            ):
                line = ser_line[: -len(TERMINATOR)]
                temps = line.split(",", self._channels - 1)
                for i in range(self._channels):
                    if self._test_val(self._preamble_str[i], temps[i]):
                        try:
                            self._tmp_temperature[i] = float(temps[i][PREAMBLE_SIZE:])
                        except ValueError:
                            err = "Temperature data error. Could not convert value(s) to float."
                            self._message(
                                "Failed to convert temperature channel value to float."
                            )
                    else:
                        err = "Malformed response. Channel preamble or channel data incorrect."
                    self.temperature[i] = self._tmp_temperature[i]
            else:
                err = "Malformed response. Terminator or line size incorrect."

        self.output = []
        self.output.append(time.time())
        self.output.append(err)
        for i in range(self._channels):
            self.output.append(self.temperature[i])
