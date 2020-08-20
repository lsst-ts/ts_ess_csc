# This file is part of ts_ess.
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

__all__ = ["EssCsc"]

import asyncio
import pathlib

from lsst.ts import salobj
from lsst.ts.ess.mock.mock_temperature_sensor import MockTemperatureSensor
from lsst.ts.ess.ESS_temperature_4ch_reader import ESS_Temperature_4ch

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

    def __init__(
        self, config_dir=None, initial_state=salobj.State.STANDBY, simulation_mode=0,
    ):
        schema_path = pathlib.Path(__file__).resolve().parents[4].joinpath("schema", "ess.yaml")
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

        self.log.info("__init__")

        self._ess_sensor = None
        self.temperature_task = None

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
                self._ess_sensor.readInstrument()
                data = {}
                data["timestamp"] = salobj.current_tai()
                data["temperatureC01"] = self._ess_sensor.temperature_c00
                data["temperatureC02"] = self._ess_sensor.temperature_c01
                data["temperatureC03"] = self._ess_sensor.temperature_c02
                data["temperatureC04"] = self._ess_sensor.temperature_c03
                self.log.info(f"Sending telemetry {data}")
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
            self._ess_sensor = MockTemperatureSensor()
        else:
            self.log.info("Connecting to the sensor.")
            self._ess_sensor = ESS_Temperature_4ch(
                self.config.uart, self.config.baudrate, self.config.connection_timeout
            )
            self._ess_sensor.serial_open()
            self.log.info("Connection to the sensor established.")

        self.log.info("Start periodic polling of the sensor data.")
        self.temperature_task = asyncio.create_task(self.get_temperature(TEMPERATURE_POLLING_INTERVAL))

    async def disconnect(self):
        """Disconnect from the ESS sensor, if connected, and stop the mock
        sensor, if running.
        """
        self.log.info("Disconnecting")
        if self.temperature_task:
            self.temperature_task.cancel()
        self._ess_sensor = None

    async def handle_summary_state(self):
        """Override of the handle_summary_state function to connect or
        disconnect to the ESS sensor (or the mock_controller) when needed.
        """
        self.log.info(f"handle_summary_state {salobj.State(self.summary_state).name}")
        if self.disabled_or_enabled:
            if not self.connected:
                await self.connect()
        else:
            await self.disconnect()

    async def configure(self, config):
        self.config = config

    async def implement_simulation_mode(self, simulation_mode):
        if simulation_mode not in (0, 1):
            raise salobj.ExpectedError(f"Simulation_mode={simulation_mode} must be 0 or 1")

    @property
    def connected(self):
        if self._ess_sensor is None:
            return False
        return True

    @staticmethod
    def get_config_pkg():
        return "ts_config_ocs"

    @classmethod
    def add_arguments(cls, parser):
        super(EssCsc, cls).add_arguments(parser)
        parser.add_argument("-s", "--simulate", action="store_true", help="Run in simuation mode?")

    @classmethod
    def add_kwargs_from_args(cls, args, kwargs):
        super(EssCsc, cls).add_kwargs_from_args(args, kwargs)
        kwargs["simulation_mode"] = 1 if args.simulate else 0
