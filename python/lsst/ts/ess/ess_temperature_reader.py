""" ESS Temperature instrument reader using FTDI VCP. """
##############################################################################
# File:         ess_temperature_reader.py
#
# LSST Environmental Sensors System (ESS) multi-channel temperature instrument
# protocol converter using FTDI virtual serial port (VCP).
# Provides an ESS instrument communication class and separate thread 
# controlling instrument read.
#
# Date      Author              Comment
#-----------------------------------------------------------------------------
# 20200908  Garry Knight        First definition
#
##############################################################################
from typing import List, Any, Optional, Dict
import logging
import serial
import threading
import time

# Temperature instrument serial string data ....
PREAMBLE_SIZE: int = 4
VALUE_SIZE: int = 9
DELIM_SIZE: int = 1
SENSOR_DATA_SIZE: int = PREAMBLE_SIZE + VALUE_SIZE + DELIM_SIZE
TERMINATOR_SIZE: int = 2
DELIMITER: str = ','
TERMINATOR: str = '\r\n'
ERR_VAL = 'NaN'

logger = logging.getLogger(__name__)


class ESS_Temperature:
    """
    ESS temperature instrument protocol converter object.
    """

    def __init__(
            self,
            name: str,
            channels: int,
            uart: str,
            baudrate: int = 19200,
            timeout: float = 1.0):
        """
        Initialize an ESS SEL temperature instrument protocol converter.
        
        :param name: The name of the temperature instrument instance.
        :type name: str
        :param channels: The number of temperature instrument channels.
        :type channels: int
        :param uart: The uart name.
        :type uart: str
        :param baudrate: The UART BAUD.
        :type baudrate: int
        :param timeout: The uart read timeout in seconds.
        :type timeout: float
        """
        self._name: str = name
        self._channels: int = channels
        self._uart: str = uart
        self._baudrate: int = baudrate
        self._timeout: float = timeout
        self._first_capture: bool = True

        self.timestamp: float = None
        self.temperature: float = []
        
        self._preamble_str: str = []
        self._tmp_temperature: float = []
        for i in range(self._channels):
            self._tmp_temperature.append('NaN')
            self.temperature.append('NaN')
            self._preamble_str.append(f'C{i:02}=')
            
        self._read_line_size: int = \
                (self._channels * SENSOR_DATA_SIZE) - DELIM_SIZE

        self._serial_port = serial.Serial(self._uart)
        self._serial_port.baud = self._baudrate
        self._serial_port.timeout = timeout
        self._serial_port.rtscts = 0
        self._serial_open()
        
    def __del__(self):
        """
        Delete instance
        """
        self._serial_close()

    def _message(self, text: Any) -> None:
        """
        Print a message prefaced with the axis/controller info.

        :param text: Anything. It will be converted to string.
        :type text: Any
        :return: None
        :rtype: None
        """
        logger.debug("ESS_Temperature:{}: {}".format(self._name, text))
        print("ESS_Temperature:{}: {}".format(self._name, text))

    def _serial_open(self):
        """
        Open serial port for instrument reads.
        
        :param: None
        :type: None
        :return: None
        :rtype: None
        """
        self._serial_port.baudrate = self._baudrate
        self._serial_port.timeout = self._timeout
        self._serial_port.rtscts = 0
        self._serial_port.write_timeout = 1.0
        try:
            self._serial_port.close()
            self._serial_port.open()
            msg = self._serial_port.name + " opened."
            self._message(msg)
        except:
            msg = self._serial_port.name + " ERROR: Failed to open."
            self._message(msg)
            raise

    def _serial_close(self):
        """
        Close serial port for instrument reads.
        
        :param: None
        :type: None
        :return: None
        :rtype: None
        """
        try:
            self._serial_port.close()
            msg = self._serial_port.name + " closed." 
            self._message(msg)
        except:
            msg = self._serial_port.name + " ERROR: failed to close." 
            self._message(msg)
            raise
    
    def _test_val(self, preamble, sensor_str):
        """
        Test temperature channel data string.
        Returns float channel value if pass, float ERR_VAL if fail.
        
        :param preamble: Preamble string for channel data (eg."C01=")
        :type preamble: str
        :param sensor_str: Sensor channel data string (eg."C01=0001.4500")
        :type sensor_str: str
        :return: Temperature value
        :rtype: float
        """
        val: float = ERR_VAL
        if sensor_str[0:PREAMBLE_SIZE] == preamble:
            val = float(sensor_str[PREAMBLE_SIZE:SENSOR_DATA_SIZE - 1])
        return val

    def read_instrument(self):
        """
        Read temperature instrument.
        Reads instrument, tests data and populates temperature channel data
        if no errors are found.
        A timestamp is also updated following successful conversion of
        channel data.
        
        :return: None
        :rtype: None
        """
        ser_line = self._serial_port.readline()
        if not self._first_capture:
            line = ''
            line = ser_line.decode('utf-8')[:-2]
            if len(line) == self._read_line_size:
                temps = line.split(',', self._channels-1)
                err_flag: bool = False
                for i in range(self._channels):
                    if self._test_val(self._preamble_str[i], temps[i]):
                        self._tmp_temperature[i] = float(temps[i][PREAMBLE_SIZE:])
                    else:
                        err_flag = True
                if err_flag:
                    raise ValueError(self._name, ':',
                            'Temperature data error.')
                else:
                    for i in range(self._channels):
                        self.temperature[i] = self._tmp_temperature[i]
                    self.timestamp = time.time()
                    print(self.timestamp, self.temperature)
            else:
                raise ValueError(self._name, ':',
                        'Serial timeout or received line length error.')
        else:
            self._first_capture = False


class InstrumentThread (threading.Thread):
    """
        Instrument read loop thread.
    """
    def __init__(self, name: str, instr):
        """
        Initialize instrument read  loop thread.

        :param text: Anything. It will be converted to string.
        :type text: Any
        :return: None.
        :rtype: None
        """
        self._ess_instrument = instr
        threading.Thread.__init__(self)
        self.enabled: bool = True
        self._name: str = name
        self.counter: int = 0
        self.run()

    def _message(self, text: Any) -> None:
        """
        Print a message prefaced with the axis/controller info.

        :param text: Anything. It will be converted to string.
        :type text: Any
        :return: None.
        :rtype: None
        """
        logger.debug("ESSInstrumentThread:{}: {}".format(self._name, text))
        print("ESSInstrumentThread:{}: {}".format(self._name, text))

    def terminate(self):
        """
        Terminate the instrument read loop.

        :return: None.
        :rtype: None
        """
        msg = "Stopping instrument read loop for:" \
                + self._ess_instrument._name + "."
        self._message(msg)
        self.enabled = False
        
    def run(self):     
        """
        Run the instrument read loop.
        
        :return: None.
        :rtype: None
        """
        msg = "Starting instrument read loop for:" \
                + self._ess_instrument._name + "."
        self._message(msg)
        while self.enabled:
            self._ess_instrument.read_instrument()
            self.counter = self.counter + 1
