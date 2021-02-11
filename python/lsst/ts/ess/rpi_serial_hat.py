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

"""Implementation of Raspberry Pi 4 serial communication hat.
"""

__all__ = 'RpiSerialHat'

from typing import Any, Dict
import logging
import RPi.GPIO as gpio
import serial
import time
from threading import RLock


logging.basicConfig(
    # Configure logging used for printing debug messages.
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.DEBUG,
    datefmt='%Y-%m-%d %H:%M:%S')

logger = logging.getLogger(__name__)


class RpiSerialHat:
    r"""LSST Serial port using RPi4 serial hat.

    Parameters
    ----------
    name : 'str'
        Identifier for the object.
    port_id : 'str'
        Serial port identifier.
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
    IndexError if attempted multiple use of serial port.
    IndexError if attempted multiple use of instance name.
    """

    _instances: Dict[str, 'RpiSerialHat'] = {}
    _used_ports: Dict[str, 'RpiSerialHat'] = {}

    # Define serial hub unit port identifiers
    SERIAL_CH_1: str = 'serial_ch_1'
    SERIAL_CH_2: str = 'serial_ch_2'
    SERIAL_CH_3: str = 'serial_ch_3'
    SERIAL_CH_4: str = 'serial_ch_4'
    SERIAL_CH_5: str = 'serial_ch_5'

    # Define gpio channel numbers (Broadcomm mode)
    PIN_U4_ON: int = 17
    PIN_U4_DOUT: int = 18
    PIN_U4_DIRN: int = 3
    PIN_U5_ON: int = 23
    PIN_U5_DIN: int = 24
    PIN_U6_ON: int = 11
    PIN_U6_DIN: int = 7
    gpio.setmode(gpio.BCM)
    gpio.setwarnings(False)

    # Define gpio pin state control
    STATE_TRX_ON: bool = True
    STATE_TRX_OFF: bool = False

    STATE_DIRN_TX: bool = True
    STATE_DIRN_RX: bool = False
    STATE_DOUT_HI: bool = True
    STATE_DOUT_LO: bool = False

    # Define serial transceiver module UART's and pins, then map to physical connectors.
    # serial device, module ON pin, module DIN pin, module DOUT pin, module DIRN pin (RS-422).
    u4_ser1_config = '/dev/ttyS0', PIN_U4_ON, None, PIN_U4_DOUT, PIN_U4_DIRN
    u5_ser1_config = '/dev/ttyAMA2', PIN_U5_ON, PIN_U5_DIN, None, None
    u5_ser2_config = '/dev/ttyAMA3', PIN_U5_ON, PIN_U5_DIN, None, None
    u6_ser1_config = '/dev/ttyAMA1', PIN_U6_ON, PIN_U6_DIN, None, None
    u6_ser2_config = '/dev/ttyAMA4', PIN_U6_ON, PIN_U6_DIN, None, None

    serial_ports = {SERIAL_CH_1: u4_ser1_config,
                    SERIAL_CH_2: u6_ser1_config,
                    SERIAL_CH_3: u5_ser1_config,
                    SERIAL_CH_4: u5_ser2_config,
                    SERIAL_CH_5: u6_ser2_config
                    }

    def __init__(self,
                 name: str,
                 port_id: str,
                 ):
        if name not in RpiSerialHat._instances:
            if port_id not in RpiSerialHat._used_ports:
                self.name: str = name
                self._port_id: str = port_id
                self._lock: RLock = RLock()
                self._terminator: str = '\r\n'
                self._line_size: int = 0
                self._serial_timeout: float = 1
                if self._port_id in RpiSerialHat.serial_ports:
                    self._ser_port, self._pin_on, self._pin_din, self._pin_dout, self._pin_dirn = \
                        RpiSerialHat.serial_ports[self._port_id]
                    try:
                        self._ser = serial.Serial()
                        self._ser.port = self._ser_port
                        print('Port:', self._ser.port)
                    except serial.SerialException as e:
                        self._message(e)
                        # Unrecoverable error, so propagate error
                        raise e
                    else:
                        # Setup GPIO
                        self._rpi_pin_setup(self._pin_on, gpio.OUT)
                        self._rpi_pin_setup(self._pin_dout, gpio.OUT)
                        self._rpi_pin_setup(self._pin_din, gpio.IN)
                        self._rpi_pin_setup(self._pin_dirn, gpio.OUT)

                        # Turn on transceiver module and default other pin states
                        self._rpi_pin_state(self._pin_on, RpiSerialHat.STATE_TRX_ON)
                        self._rpi_pin_state(self._pin_dout, RpiSerialHat.STATE_DOUT_LO)
                        self._rpi_pin_state(self._pin_dirn, RpiSerialHat.STATE_DIRN_RX)

                        RpiSerialHat._instances[name] = self
                        RpiSerialHat._used_ports[port_id] = self
                        logger.debug('RpiSerialHat:{}: First instantiation '
                                     'using serial channel id: "{}".'.format(name, port_id))
                else:
                    logger.debug('RpiSerialHat:{}: Error: '
                                 'A serial channel named "{}" does not exist.'
                                 .format(name, port_id))
                    raise IndexError('RpiSerialHat:{}: '
                                     'A serial channel named "{}" does not exist.'
                                     .format(name, port_id))
            else:
                logger.debug('RpiSerialHat:{}: Error: '
                             'Attempted multiple use of serial channel "{}".'
                             .format(name, port_id))
                raise IndexError('RpiSerialHat:{}: '
                                 'Attempted multiple use of serial channel "{}".'
                                 .format(name, port_id))
        else:
            logger.debug('RpiSerialHat: Error: '
                         'Attempted multiple instantiation of "{}".'.format(name))
            raise IndexError('RpiSerialHat: Error: '
                             'Attempted multiple instantiation of "{}".'.format(name))

    def __del__(self):
        self._ser.close()
        self._rpi_pin_cleanup(self._pin_on)
        self._rpi_pin_cleanup(self._pin_dout)
        self._rpi_pin_cleanup(self._pin_din)
        self._rpi_pin_cleanup(self._pin_dirn)

    @property
    def baudrate(self) -> int:
        """BAUD of the serial device ('int').
        """
        baud: int = self._ser.baud
        self._message('Serial port BAUD read: {}.'
                      .format(baud))
        return baud

    @baudrate.setter
    def baudrate(self, baud: int) -> None:
        self._ser.baudrate = baud
        self._message('Serial port BAUD set: {}.'
                      .format(baud))

    @property
    def line_size(self) -> int:
        """Serial data line size ('int').
        """
        self._message('Serial data line size read: {} characters.'
                      .format(self._line_size))
        return self._line_size

    @line_size.setter
    def line_size(self, line_size: int) -> None:
        self._line_size = line_size
        self._message('Serial data line size set: {} characters.'
                      .format(self._line_size))

    @property
    def read_timeout(self) -> float:
        """Read timeout of serial data line in seconds ('float').
        """
        read_timeout: float = self._ser.timeout
        self._message('Serial port read timeout read: {} seconds.'
                      .format(read_timeout))
        return read_timeout

    @read_timeout.setter
    def read_timeout(self, timeout: float) -> None:
        self._ser.timeout = timeout
        self._message('Serial port read timeout set: {} seconds.'
                      .format(timeout))

    @property
    def terminator(self) -> str:
        """Serial data line terminator string ('str').
        """
        self._message('Serial data line terminator string read: {}.'
                      .format(self._read_timeout))
        return self._terminator

    @terminator.setter
    def terminator(self, terminator: str) -> None:
        self._terminator = terminator
        self._message('Serial data line terminator string set.')

    def _message(self, text: Any) -> None:
        # Print a message prefaced with the object info ('Any').
        logger.debug('RpiSerialHat:{}: {}'.format(self.name, text))

    def _rpi_pin_cleanup(self, rpi_pin) -> None:
        # Clear RPi pin.
        # Ignored if pin number is None.
        if rpi_pin is not None:
            try:
                gpio.cleanup(rpi_pin)
            except RuntimeError:
                self._message('GPIO pin cleanup error.')

    def _rpi_pin_setup(self, rpi_pin: int, pin_type) -> None:
        # Setup RPi pin.
        # True = Input, False = Output.
        # ignored if pin number is None.
        if rpi_pin is not None:
            try:
                gpio.setup(rpi_pin, pin_type)
            except RuntimeError:
                self._message('Error setting up GPIO pin.')

    def _rpi_pin_state(self, rpi_pin: int, state: bool) -> None:
        # Output transceiver pin state.
        # high = True, low = False.
        # ignored if pin number is None.
        if rpi_pin is not None:
            try:
                gpio.output(rpi_pin, state)
            except RuntimeError:
                self._message('Error writing to GPIO output. GPIO channel has not been setup.')

    def open(self) -> None:
        """Open and configure serial port.
        Opens the serial communications port, sets BAUD and read timeout.

        Raises
        ------
        IOError if serial communications port fails to open.
        """
        with self._lock:
            try:
                self._ser
            except NameError:
                self._message('Cannot open. Serial port does not exist.')
                raise RuntimeWarning(
                    f"{self.name}: Could not open. Serial port does not exist."
                )
            else:
                if not self._ser.is_open:
                    try:
                        self._ser.open()
                        self._message('Serial port opened.')
                    except serial.SerialException as e:
                        self._message('Serial port open failed.')
                        raise e
                else:
                    self._message('Port already open!')

    def close(self) -> None:
        """Close serial communications port.

        Raises
        ------
        IOError if serial communications port fails to close.
        """
        with self._lock:
            try:
                self._ser
            except NameError:
                self._message('Cannot close. Serial port does not exist.')
                raise RuntimeWarning(
                    f"{self.name}: Could not close the serial port!"
                )
            else:
                if self._ser.is_open:
                    self._ser.close()
                    self._message('Serial port closed.')
                else:
                    self._message('Serial port already closed.')

    def readline(self) -> str:
        r"""Read a line of ASCII string data from the serial port.

        Returns
        -------
        error, resp : 'tuple'
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

        resp: str = ""
        err: str = "OK"
        self._rpi_pin_state(self._pin_dirn, RpiSerialHat.STATE_DIRN_RX)
        with self._lock:
            expiry_time = time.perf_counter() + self._ser.timeout
            while time.perf_counter() < expiry_time:
                try:
                    resp += str(self._ser.read(1), 'ASCII')
                except UnicodeError as e:
                    err = "Received non-ASCII data in response."
                    raise e
                except serial.SerialException as e:
                    err = "Serial exception. Serial port might be closed."
                    raise e
                finally:
                    if (len(self._terminator) > 0 and
                            resp[-len(self._terminator):] == self._terminator):
                        return err, resp
                    elif 0 < self._line_size <= len(resp):
                        return err, resp
            error = "Timed out with incomplete response."
            return err, resp
