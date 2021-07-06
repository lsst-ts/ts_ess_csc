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

__all__ = ["EssCsc"]

import argparse
import asyncio
import json
import platform
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Union

import numpy as np

from .config_schema import CONFIG_SCHEMA
from . import __version__
from lsst.ts import salobj, tcpip  # type: ignore
from lsst.ts.envsensors import (
    DeviceConfig,
    DeviceType,
    Key,
    ResponseCode,
)

"""Standard timeout in seconds for socket connections."""
SOCKET_TIMEOUT = 5


class EssCsc(salobj.ConfigurableCsc):
    """Upper level Commandable SAL Component for the Environmental Sensors
    Support.

    Parameters
    ----------
    index: `int`
        The index of the CSC
    config_dir : `str`
        The configuration directory
    initial_state : `salobj.State`
        The initial state of the CSC
    simulation_mode : `int`
        Simulation mode (1) or not (0)
    """

    valid_simulation_modes = (0, 1)
    version = __version__

    def __init__(
        self,
        index: int,
        config_dir: str = None,
        initial_state: salobj.State = salobj.State.STANDBY,
        simulation_mode: int = 0,
    ) -> None:
        self.config: Optional[SimpleNamespace] = None
        self.device_configurations: Dict[str, DeviceConfig] = {}
        self._config_dir = config_dir
        super().__init__(
            name="ESS",
            index=index,
            config_schema=CONFIG_SCHEMA,
            config_dir=config_dir,
            initial_state=initial_state,
            simulation_mode=simulation_mode,
        )

        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.host = None
        self.port = None
        self.telemetry_loop: asyncio.Future = salobj.make_done_future()
        self.last_commands: List[str] = []

        self.log.info("ESS CSC created.")

    async def _read_loop(self) -> None:
        """Execute a loop that reads incoming data from the SocketServer."""
        try:
            while True:
                data = await self.read()
                if Key.RESPONSE in data:
                    response = data[Key.RESPONSE]
                    if response != ResponseCode.OK:
                        try:
                            oldest_last_command = self.last_commands.pop(0)
                            self.log.error(
                                f"Command {oldest_last_command} received response {response}. Continuing."
                            )
                        except IndexError:
                            self.log.error(
                                f"Received response {data} while no command was waiting for a reply."
                            )
                elif Key.TELEMETRY in data:
                    sensor_data = data[Key.TELEMETRY]
                    await self.get_telemetry(data=sensor_data)
                else:
                    raise ValueError(f"Unknown data {data!r} received.")
        except Exception:
            self.log.exception("_read_loop failed")

    async def read(self) -> dict:
        """Utility function to read a string from the reader and unmarshal it

        Returns
        -------
        data : `dict`
            A dictionary with objects representing the string read.
        """
        if not self.reader or not self.connected:
            raise RuntimeError("Not connected")

        read_bytes = await asyncio.wait_for(
            self.reader.readuntil(tcpip.TERMINATOR), timeout=SOCKET_TIMEOUT
        )
        data = json.loads(read_bytes.decode())
        return data

    async def write(self, command: str, **data: Any) -> None:
        """Write the command and data appended with a newline character.

        Parameters
        ----------
        command: `str`
            The command to write.
        data: `dict`
            The data to write.
        """
        if not self.writer or not self.connected:
            raise RuntimeError("Not connected")

        st = json.dumps({"command": command, **data})
        self.last_commands.append(st)
        self.writer.write(st.encode() + tcpip.TERMINATOR)
        await self.writer.drain()

    async def get_telemetry(self, data: List[Union[str, int, float]]) -> None:
        """Get the timestamp and temperatures from the output data.

        Parameters
        ----------
        data: `list`
            A list containing the timestamp, error and temperatures as
            measured by the sensor. The order of the items in the list is:
            - Sensor name: `str`
            - Timestamp: `float`
            - Response code: `int`
            - One or more sensor data: each of type `float`
        """
        try:
            sensor_name = data[0]
            timestamp = data[1]
            error_code = data[2]
            device_configuration = self.device_configurations[sensor_name]
            if error_code == ResponseCode.OK:
                telemetry = {"sensor_name": sensor_name, "timestamp": timestamp}
                sensor_data = data[3:]
                if len(sensor_data) != device_configuration.num_channels:
                    raise RuntimeError(
                        f"Expected {device_configuration.num_channels} temperatures "
                        f"but received {len(sensor_data)}."
                    )
                for i, value in enumerate(sensor_data):
                    # The telemetry channels start counting at 1 and not 0.
                    telemetry[f"temperatureC{i+1:02d}"] = value
                self.log.info(f"Received temperatures {telemetry}")
                self.log.info("Sending telemetry.")
                telemetry_method = getattr(
                    self, f"tel_temperature{device_configuration.num_channels}Ch"
                )
                telemetry_method.set_put(**telemetry)
        except Exception:
            self.log.exception("Method get_telemetry() failed")

    async def connect(self) -> None:
        """Determine if running in local or remote mode and dispatch to the
        corresponding connect coroutine.
        """
        self.log.info("Connecting")
        self.log.info(self.config)
        self.log.info(f"self.simulation_mode = {self.simulation_mode}")
        if self.config is None:
            raise RuntimeError("Not yet configured")
        if self.connected:
            raise RuntimeError("Already connected")

        await self.connect_socket()

    async def connect_socket(self) -> None:
        """Connect to the SocketServer and send the configuration for which
        sensors to start reading the data of."""
        if not self.config:
            raise RuntimeError("Not configured yet.")
        if not self.host:
            self.host = self.config.host
        if not self.port:
            self.port = self.config.port
        rw_coro = asyncio.open_connection(host=self.host, port=self.port)
        self.reader, self.writer = await asyncio.wait_for(
            rw_coro, timeout=SOCKET_TIMEOUT
        )
        configuration = {"devices": self.config.devices}
        await self.write(
            command="configure",
            parameters={"configuration": configuration},
        )

        # Start a loop to read incoming data from the SocketServer.
        self.telemetry_loop = asyncio.create_task(self._read_loop())

    async def begin_enable(self, id_data) -> None:
        """Begin do_enable; called before state changes.

        This method sends a CMD_INPROGRESS signal.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data

        """
        await super().begin_enable(id_data)
        self.cmd_enable.ack_in_progress(id_data, timeout=60)

    async def end_enable(self, id_data) -> None:
        """End do_enable; called after state changes but before command
        acknowledged.

        This method connects to the ESS Instrument and starts it.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data
        """
        if not self.connected:
            await self.connect()

        self.log.info("Start periodic polling of the sensor data.")
        await self.write(command="start", parameters={})
        await super().end_enable(id_data)

    async def begin_disable(self, id_data) -> None:
        """Begin do_disable; called before state changes.

        This method will try to gracefully stop the ESS Instrument and then
        disconnect from it.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data
        """
        self.cmd_disable.ack_in_progress(id_data, timeout=60)

        await self.write(command="stop", parameters={})
        self.telemetry_loop.cancel()
        await self.write(command="disconnect", parameters={})

        await super().begin_disable(id_data)

    async def configure(self, config) -> None:
        """Configure the CSC.

        Also store the device configurations for easier access when receiving
        and processing telemetry.

        Parameters
        ----------
        config : `object`
            The configuration as described by the schema at
            `lsst.ts.ess.CONFIG_SCHEMA`, as a struct-like object.
        """
        self.config = config
        for device in config.devices:
            if device[Key.DEVICE_TYPE] == DeviceType.FTDI:
                dev_id = Key.FTDI_ID
            elif device[Key.DEVICE_TYPE] == DeviceType.SERIAL:
                dev_id = Key.SERIAL_PORT
            else:
                raise ValueError(f"Unknown device type {device[Key.TYPE]} encountered.")
            self.device_configurations[device[Key.NAME]] = DeviceConfig(
                name=device[Key.NAME],
                num_channels=device[Key.CHANNELS],
                dev_type=device[Key.DEVICE_TYPE],
                dev_id=device[dev_id],
                sens_type=device[Key.SENSOR_TYPE],
            )

    @property
    def connected(self) -> bool:
        return not (
            self.reader is None
            or self.writer is None
            or self.reader.at_eof()
            or self.writer.is_closing()
        )

    @staticmethod
    def get_config_pkg() -> str:
        return "ts_config_ocs"
