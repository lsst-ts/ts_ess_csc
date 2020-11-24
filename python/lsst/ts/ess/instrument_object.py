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
"""Implementation of ESS Instrument object."""
from typing import Any, Dict
import logging
from threading import Thread

logging.basicConfig(
    # Configure logging used for printing debug messages.
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.DEBUG,
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


def _threaded(fn):
    # Thread wrapper used to decorate control methods
    def _wrapper(*args, **kwargs):
        thread = Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
        return thread

    return _wrapper


class Instrument:
    """Instrument read-loop thread.

    Parameters
    ----------
    name : 'str'
        Name of the Instrument instance.
    reader : 'reader'
        Device read instance.
    callback_func : 'func'
        Callback function to receive instrument output.

    Raises
    ------
    IndexError if attempted multiple use of instance name.
    IndexError if attempted multiple use of serial device instance.
    """

    _instances: Dict[str, "Instrument"] = {}
    _devices: Dict[str, "Instrument"] = {}

    def __init__(self, name: str, reader, callback_func):
        if name not in Instrument._instances:
            if reader.serial_port not in Instrument._devices:
                logger.debug(
                    "Instrument:{}: First instantiation "
                    'using serial reader "{}".'.format(name, reader.name)
                )
                self._reader = reader
                self._enabled: bool = False
                self.name: str = name
                self._callback_func = callback_func
                self.start()

                Instrument._instances[name] = self
                Instrument._devices[reader.serial_port] = self
            else:
                logger.debug(
                    "Instrument:{}: Error: "
                    'Attempted multiple use of reader serial device instance "{}".'.format(
                        name, reader.serial_port
                    )
                )
                raise IndexError(
                    "Instrument:{}: "
                    'Attempted multiple use of reader serial device instance "{}".'.format(
                        name, reader.serial_port
                    )
                )
        else:
            logger.debug(
                "Instrument: Error: "
                'Attempted multiple instantiation of "{}".'.format(name)
            )
            raise IndexError(
                "Instrument: Error: "
                'Attempted multiple instantiation of "{}".'.format(name)
            )

    def _message(self, text: Any) -> None:
        # Print a message prefaced with the InstrumentThread object info.
        logger.debug("Instrument:{}: {}".format(self.name, text))

    def start(self):
        """Start the instrument read loop.
        """
        msg = 'Starting read thread for "{}" instrument.'.format(self._reader.name)
        self._message(msg)
        self._enabled = True
        self._run()

    def stop(self):
        """Terminate the instrument read loop.
        """
        msg = 'Stopping read thread for "{}" instrument.'.format(self._reader.name)
        self._message(msg)
        self._enabled = False

    @_threaded
    def _run(self):
        """Run threaded instrument read loop.

        If enabled, loop and read the serial instrument and pass result to
        callback_func function.
        """
        while self._enabled:
            self._reader.read()
            self._callback_func(self._reader.output)
