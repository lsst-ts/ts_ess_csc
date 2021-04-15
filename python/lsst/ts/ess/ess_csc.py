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

import asyncio
import platform

import numpy as np

from .config_schema import CONFIG_SCHEMA
from . import __version__
from lsst.ts import salobj
from lsst.ts.ess.mock.mock_temperature_sensor import MockTemperatureSensor
from lsst.ts.ess.ess_instrument_object import EssInstrument
from .sel_temperature_reader import SelTemperature

TEMPERATURE_POLLING_INTERVAL = 0.25


class EssCsc(salobj.ConfigurableCsc):
    """Upper level Commandable SAL Component for the Environmental Sensors
    Support.

    Parameters
    ----------
    index: `int`
        The index of the CSC
    config_dir : `string`
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
        index,
        config_dir=None,
        initial_state=salobj.State.STANDBY,
        simulation_mode=0,
    ):
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

        self.device = None
        self.ess_instrument = None

        # Unit tests may set this to an integer value to simulate a
        # disconnected or missing sensor.
        self.nan_channel = None

        self.log.info("ESS CSC created.")

    async def get_telemetry(self, output):
        """Get the timestamp and temperatures from the data.

        Parameters
        ----------
        output: array
            An array containing the timestamp, error and temperatures as
            measured by the sensors.
        """
        try:
            self.log.debug("Getting the temperature from the sensor")
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
            self.log.exception("Method get_temperature() failed")

    async def connect(self):
        """Connect to the ESS sensor or start the mock sensor, if in
        simulation mode.
        """
        self.log.info("Connecting")
        self.log.info(self.config)
        self.log.info(f"self.simulation_mode = {self.simulation_mode}")
        if self.config is None:
            raise RuntimeError("Not yet configured")
        if self.connected:
            raise RuntimeError("Already connected")

        self.log.info("Connecting to the sensor.")
        self._get_device()
        sel_temperature = SelTemperature(
            self.config.name, self.device, self.config.channels, self.log
        )
        self.ess_instrument = EssInstrument(
            self.config.name, sel_temperature, self.get_telemetry, self.log
        )
        self.log.info("Connection to the sensor established.")

    async def begin_enable(self, id_data):
        """Begin do_enable; called before state changes.

        This method sends a CMD_INPROGRESS signal.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data

        """
        await super().begin_enable(id_data)
        self.cmd_enable.ack_in_progress(id_data, timeout=60)

    async def end_enable(self, id_data):
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
        await self.ess_instrument.start()
        await super().end_enable(id_data)

    async def begin_disable(self, id_data):
        """Begin do_disable; called before state changes.

        This method will try to gracefully stop the ESS Instrument and then
        disconnect from it.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data
        """
        self.cmd_disable.ack_in_progress(id_data, timeout=60)
        try:
            await self.ess_instrument.stop()
        except Exception:
            self.log.exception("Error in begin_disable. Continuing...")

        await self.disconnect()
        await super().begin_disable(id_data)

    async def disconnect(self):
        """Disconnect from the ESS sensor, if connected, and stop the mock
        sensor, if running.
        """
        self.log.info("Disconnecting")
        self.ess_instrument = None

    async def configure(self, config):
        self.config = config

    @property
    def connected(self):
        if self.ess_instrument is None:
            return False
        return True

    @staticmethod
    def get_config_pkg():
        return "ts_config_ocs"

    def _get_device(self):
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
