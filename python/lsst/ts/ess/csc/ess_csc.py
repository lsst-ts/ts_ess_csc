# This file is part of ts_ess_csc.
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
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

__all__ = ["EssCsc"]

import asyncio
import math
import types
from typing import Dict, List, Optional

from .base_model import BaseModel, get_model_class
from .config_schema import CONFIG_SCHEMA
from . import __version__
from lsst.ts import salobj, utils
from lsst.ts.ess import common
from lsst.ts.idl.enums.ESS import ErrorCode

SOCKET_TIMEOUT = 5
"""Standard timeout in seconds for socket connections."""

NUMBER_OF_TEMPERATURE_CHANNELS = 16
"""The number of temperature channels expected in the telemetry."""

TEMPERATURE_NANS = [math.nan] * NUMBER_OF_TEMPERATURE_CHANNELS
"""Initial array with NaN values in which the temperature values of
the sensors will be stored."""


class EssCsc(salobj.ConfigurableCsc):
    """Upper level Commandable SAL Component for the Environmental Sensors
    Support.

    Parameters
    ----------
    index : `int`
        The index of the CSC
    config_dir : `str`
        The configuration directory
    initial_state : `salobj.State`
        The initial state of the CSC
    simulation_mode : `int`
        Simulation mode (1) or not (0)
    settings_to_apply : `str`, optional
        Settings to apply if ``initial_state`` is `State.DISABLED`
        or `State.ENABLED`.
    """

    enable_cmdline_state = True
    valid_simulation_modes = (0, 1)
    version = __version__

    def __init__(
        self,
        index: int,
        config_dir: str = None,
        initial_state: salobj.State = salobj.State.STANDBY,
        simulation_mode: int = 0,
        settings_to_apply: str = "",
    ) -> None:
        self.config: Optional[types.SimpleNamespace] = None
        self.device_configurations: Dict[str, common.DeviceConfig] = {}
        self._config_dir = config_dir
        self.models: List[BaseModel] = list()
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.telemetry_loop: asyncio.Future = utils.make_done_future()
        self.last_commands: List[str] = []
        self.start_models_task = utils.make_done_future()
        self.run_models_task = utils.make_done_future()
        self.stop_models_tasks: List[asyncio.Task] = []

        super().__init__(
            name="ESS",
            index=index,
            config_schema=CONFIG_SCHEMA,
            config_dir=config_dir,
            initial_state=initial_state,
            simulation_mode=simulation_mode,
            settings_to_apply=settings_to_apply,
        )
        self.log.info("ESS CSC created.")

    async def begin_enable(self, id_data) -> None:
        """Begin do_enable; called before state changes.

        This override sends a CMD_INPROGRESS signal.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data

        """
        await super().begin_enable(id_data)
        self.cmd_enable.ack_in_progress(id_data, timeout=60)

    async def handle_summary_state(self) -> None:
        if self.summary_state == salobj.State.ENABLED:
            await self.start_models()
        else:
            await self.stop_models()

    async def start_models(self) -> None:
        try:
            tasks = [asyncio.create_task(model.start()) for model in self.models]
            self.start_models_task = asyncio.gather(*tasks)
            await self.start_models_task
            self.run_models_task = asyncio.create_task(self.run_models())
        except Exception as e:
            # TODO: base the error code on the exception raised
            # (though I think there are more error codes than we need).
            self.fault(
                ErrorCode.TelemetryError,
                report=f"start_models failed: {e!r}",
            )
            raise

    async def run_models(self) -> None:
        """Read and publish environmental data."""
        try:
            tasks = [model.run_task for model in self.models]
            self.run_models_task = asyncio.gather(*tasks)
            await self.run_models_task
        except Exception as e:
            # TODO: base the error code on the exception raised
            # (though I think there are more error codes than we need).
            self.fault(
                ErrorCode.TelemetryError,
                report=f"run_models failed: {e!r}",
            )
            raise

    async def stop_models(self) -> None:
        """Stop reading and publishing environmental data."""
        self.start_models_task.cancel()
        self.run_models_task.cancel()
        for task in self.stop_models_tasks:
            task.cancel()

        self.stop_models_tasks = [
            asyncio.create_task(model.stop()) for model in self.models
        ]
        await asyncio.gather(*self.stop_models_tasks, return_exceptions=True)
        failed_task_strs = [
            str(model)
            for model, task in zip(self.models, self.stop_models_tasks)
            if not task.cancelled() and task.exception() is not None
        ]
        if failed_task_strs:
            failed_summary = ", ".join(failed_task_strs)
            self.log.warning(f"Failed to stop models: {failed_summary}; continuing")

    async def stop_tasks(self):
        await super().stop_tasks()
        await self.stop_models()

    async def configure(self, config) -> None:
        """Configure the CSC.

        Also store the device configurations for easier access when receiving
        and processing telemetry.

        Parameters
        ----------
        config : `types.SimpleNamespace`
            The configuration as described by the schema at
            `lsst.ts.ess.csc.CONFIG_SCHEMA`, as a struct-like object.
        """
        for instance in config.instances:
            if instance["sal_index"] == self.salinfo.index:
                break
        else:
            raise RuntimeError(f"No config found for sal_index={self.salinfo.index}")
        for model_data in instance["models"]:
            model_class = get_model_class(model_data["model_class"])
            config_schema = model_class.get_config_schema()
            validator = salobj.DefaultingValidator(config_schema)
            model_config_dict = model_data["config"]
            model_config_dict = validator.validate(model_config_dict)
            if not isinstance(model_config_dict, dict):
                raise RuntimeError(
                    f"Config for {model_class}: {model_config_dict} is not a dict"
                )
            model_config = types.SimpleNamespace(**model_config_dict)
            model = model_class(
                config=model_config,
                topics=self,
                log=self.log,
                simulation_mode=self.simulation_mode,
            )
            self.models.append(model)

    @staticmethod
    def get_config_pkg() -> str:
        return "ts_config_ocs"
