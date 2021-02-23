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

__all__ = ["EssCsc"]

import asyncio
import platform
import pathlib

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
        self, config_dir=None, initial_state=salobj.State.STANDBY, simulation_mode=0,
    ):
        schema_path = (
            pathlib.Path(__file__).resolve().parents[4].joinpath("schema", "ess.yaml")
        )
        self.config = None
        self._config_dir = config_dir
        super().__init__(
            name="ESS",
            index=0,
            schema_path=schema_path,
            config_dir=config_dir,
            initial_state=initial_state,
            simulation_mode=simulation_mode,
        )

        self.ess_sensor = None
        self.temperature_task = None

        self.log.info("ESS CSC created.")

    async def get_temperature(self, interval):
        """Get the temperature forever at the specified interval.

        Parameters
        ----------
        interval: `float`
            The interval (sec) at which to get the temperature.
        """
        try:
            while True:
                self.log.debug("Getting the temperature from the sensor")
                self.ess_sensor.read_instrument()
                data = {
                    "timestamp": self.ess_sensor.timestamp,
                    "temperatureC01": self.ess_sensor.temperature[0],
                    "temperatureC02": self.ess_sensor.temperature[1],
                    "temperatureC03": self.ess_sensor.temperature[2],
                    "temperatureC04": self.ess_sensor.temperature[3],
                }
                self.log.info(f"Received temperatures {data}")
                if not (
                    self.ess_sensor.temperature[0] == "NaN"
                    or self.ess_sensor.temperature[1] == "NaN"
                    or self.ess_sensor.temperature[2] == "NaN"
                    or self.ess_sensor.temperature[3] == "NaN"
                ):
                    self.log.info("Sending telemetry.")
                    self.tel_temperature4Ch.set_put(**data)
                await asyncio.sleep(interval)
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
        if self.simulation_mode == 1:
            self.log.info("Connecting to the mock sensor.")
            self.ess_sensor = MockTemperatureSensor()
        else:
            self.log.info("Connecting to the sensor.")
            device = self._get_device()
            sel_temperature = SelTemperature(
                self.config.name, device, self.config.channels
            )
            self.ess_sensor = EssInstrument(self.config.name, sel_temperature, None)
            self.log.info("Connection to the sensor established.")

        self.log.info("Start periodic polling of the sensor data.")
        self.temperature_task = asyncio.create_task(
            self.get_temperature(TEMPERATURE_POLLING_INTERVAL)
        )

    async def disconnect(self):
        """Disconnect from the ESS sensor, if connected, and stop the mock
        sensor, if running.
        """
        self.log.info("Disconnecting")
        if self.temperature_task:
            self.temperature_task.cancel()
        self.ess_sensor = None

    async def handle_summary_state(self):
        """Override of the handle_summary_state function to connect or
        disconnect to the ESS sensor (or the mock_controller) when needed.
        """
        self.log.info(f"handle_summary_state {self.summary_state.name}")
        if self.disabled_or_enabled:
            if not self.connected:
                await self.connect()
        else:
            await self.disconnect()

    async def configure(self, config):
        self.config = config

    @property
    def connected(self):
        if self.ess_sensor is None:
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
        device = None
        if self.config.type == "FTDI":
            from .vcp_ftdi import VcpFtdi

            device = VcpFtdi(self.config.name, self.config.ftdi_id)
        elif self.config.type == "Serial":
            # make sure we are on a Raspberry Pi4
            if "aarch64" in platform.platform():
                from .rpi_serial_hat import RpiSerialHat

                device = RpiSerialHat(self.config.name, self.config.port)

        if device is None:
            raise RuntimeError(
                f"Could not get a {self.config.type!r} device on architecture {platform.platform()}. "
                f"Please check the configuration."
            )
        return device
