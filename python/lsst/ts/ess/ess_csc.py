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

import numpy as np

from .config_schema import CONFIG_SCHEMA
from . import __version__
from .ess_instrument_object import EssInstrument
from .mock.mock_temperature_sensor import MockTemperatureSensor
from .sel_temperature_reader import SelTemperature
from lsst.ts import salobj, tcpip

"""The temperature polling interval."""
TEMPERATURE_POLLING_INTERVAL = 0.25

"""Standard timeout in seconds for socket connections."""
SOCKET_TIMEOUT = 5

"""Constant strings that can be found in data coming from the SocketServer."""
RESPONSE = "response"
TELEMETRY = "telemetry"


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
        local_mode: bool = False,
        config_dir: str = None,
        initial_state: salobj.State = salobj.State.STANDBY,
        simulation_mode: int = 0,
    ) -> None:
        self.config = None
        self._config_dir = config_dir
        super().__init__(
            name="ESS",
            index=index,
            config_schema=CONFIG_SCHEMA,
            config_dir=config_dir,
            initial_state=initial_state,
            simulation_mode=simulation_mode,
        )

        # Temporary mode during transition to remote mode only.
        self.local_mode = local_mode

        # Used if self.local_mode == True
        self.device = None
        self.ess_instrument = None

        # Used if self.local_mode == False
        self.reader = None
        self.writer = None
        self.host = None
        self.port = None
        self.telemetry_loop = salobj.make_done_future()
        self.last_commands = []

        # Unit tests may set this to an integer value to simulate a
        # disconnected or missing sensor.
        self.nan_channel = None

        self.log.info("ESS CSC created.")

    async def _read_loop(self) -> None:
        """Execute a loop that reads incoming data from the SocketServer."""
        try:
            while True:
                data = await self.read()
                if RESPONSE in data:
                    # TODO: Properly support command responses (DM-30265)
                    response = data[RESPONSE]
                    if response != 0:
                        try:
                            oldest_last_command = self.last_commands.pop(0)
                            self.log.error(
                                f"Command {oldest_last_command} received response {response}. Continuing."
                            )
                        except IndexError:
                            self.log.error(
                                f"Received response {data} while no command was waiting for a reply."
                            )
                if TELEMETRY in data:
                    # TODO: Properly support multiple sensors (DM-30265)
                    output = data[TELEMETRY][1:]
                    await self.get_telemetry(output=output)
        except Exception:
            self.log.exception("_read_loop failed")

    async def read(self) -> dict:
        """Utility function to read a string from the reader and unmarshal it

        Returns
        -------
        data : `dict`
            A dictionary with objects representing the string read.
        """
        read_bytes = await asyncio.wait_for(
            self.reader.readuntil(tcpip.TERMINATOR), timeout=SOCKET_TIMEOUT
        )
        data = json.loads(read_bytes.decode())
        return data

    async def write(self, **data: dict) -> None:
        """Write the data appended with a newline character.

        Parameters
        ----------
        data: `dict`
            The data to write.
        """
        st = json.dumps({**data})
        self.last_commands.append(st)
        self.writer.write(st.encode() + tcpip.TERMINATOR)
        await self.writer.drain()

    async def get_telemetry(self, output: list) -> None:
        """Get the timestamp and temperatures from the output data.

        Parameters
        ----------
        output: `list`
            An array containing the timestamp, error and temperatures as
            measured by the sensor.
        """
        try:
            data = {"timestamp": output[0]}
            error_code = output[1]
            if error_code == "OK":
                for i in range(2, 2 + self.config.channels):
                    # The telemetry channels start counting at 1 and not 0.
                    data[f"temperatureC{i-1:02d}"] = (
                        float.nan if np.isnan(output[i]) else output[i]
                    )
                self.log.info(f"Received temperatures {data}")
                self.log.info("Sending telemetry.")
                telemetry_method = getattr(
                    self, f"tel_temperature{self.config.channels}Ch"
                )
                telemetry_method.set_put(**data)
        except Exception:
            self.log.exception("Method get_telemetry() failed")

    async def connect(self) -> None:
        """Determine if running in local or remote mode and dispatch to the
        corresponding connect coroutine.
        """
        self.log.info("Connecting")
        self.log.info(self.config)
        self.log.info(f"self.simulation_mode = {self.simulation_mode}")
        self.log.info(f"self.local_mode = {self.local_mode}")
        if self.config is None:
            raise RuntimeError("Not yet configured")
        if self.connected:
            raise RuntimeError("Already connected")

        if self.local_mode:
            await self.connect_local_mode()
        else:
            await self.connect_socket()

    async def connect_local_mode(self) -> None:
        """Connect to the ESS sensor or start the mock sensor, if in
        simulation mode.
        """
        self.log.info("Connecting to the local sensor.")
        self._get_device()
        sel_temperature = SelTemperature(
            self.config.name, self.device, self.config.channels, self.log
        )
        self.ess_instrument = EssInstrument(
            self.config.name, sel_temperature, self.get_telemetry, self.log
        )
        self.log.info("Connection to the local sensor established.")

    async def connect_socket(self) -> None:
        """Connect to the SocketServer and send the configuration for which
        sensors to start reading the data of."""
        if not self.host:
            self.host = self.config.host
        if not self.port:
            self.port = self.config.port
        rw_coro = asyncio.open_connection(host=self.host, port=self.port)
        self.reader, self.writer = await asyncio.wait_for(
            rw_coro, timeout=SOCKET_TIMEOUT
        )
        # TODO: Properly support multiple sensors (DM-30265)
        configuration = {
            "devices": [
                {
                    "name": self.config.name,
                    "channels": self.config.channels,
                    "type": self.config.type,
                    "ftdi_id": self.config.ftdi_id,
                }
            ]
        }
        await self.write(
            command="configure", parameters={"configuration": configuration}
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
        if self.local_mode:
            await self.ess_instrument.start()
        else:
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
        if self.local_mode:
            try:
                await self.ess_instrument.stop()
            except Exception:
                self.log.exception("Error in begin_disable. Continuing...")
        else:
            await self.write(command="stop", parameters={})
            self.telemetry_loop.cancel()
            await self.write(command="disconnect", parameters={})

        await self.disconnect()
        await super().begin_disable(id_data)

    async def disconnect(self) -> None:
        """Disconnect from the ESS sensor, if connected, and stop the mock
        sensor, if running.
        """
        self.log.info("Disconnecting")
        self.ess_instrument = None

    async def configure(self, config) -> None:
        """Configure the CSC.

        Parameters
        ----------
        config : `object`
            The configuration as described by the schema at ``schema_path``,
            as a struct-like object.
        """
        self.config = config

    @property
    def connected(self) -> bool:
        if self.ess_instrument is None:
            return False
        return True

    @staticmethod
    def get_config_pkg() -> str:
        return "ts_config_ocs"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add command line arguments.

        Parameters
        ----------
        parser: `argparse.ArgumentParser`
            The parser that parses the command line arguments.
        """
        parser.add_argument(
            "--local-mode",
            default="False",
            help="directory containing configuration files for the start command.",
            dest="local_mode",
        )
        super().add_arguments(parser)

    def _get_device(self) -> None:
        """Get the device to connect to by using the configuration of the CSC
        and by detecting whether the code is running on an aarch64 architecture
        or not.

        Returns
        -------
        device: `VcpFtdi` or `RpiSerialHat` or `None`


        Raises
        ------

        """
        self.device = None
        if self.simulation_mode == 1:
            self.log.info("Connecting to the mock sensor.")
            self.device = MockTemperatureSensor(
                "MockSensor", 4, nan_channel=self.nan_channel
            )
        elif self.config.type == "FTDI":
            from .vcp_ftdi import VcpFtdi

            self.device = VcpFtdi(self.config.name, self.config.ftdi_id, self.log)
        elif self.config.type == "Serial":
            # make sure we are on a Raspberry Pi4
            if "aarch64" in platform.platform():
                from .rpi_serial_hat import RpiSerialHat

                self.device = RpiSerialHat(self.config.name, self.config.port, self.log)

        if self.device is None:
            raise RuntimeError(
                f"Could not get a {self.config.type!r} device on architecture "
                f"{platform.platform()}. Please check the configuration."
            )
