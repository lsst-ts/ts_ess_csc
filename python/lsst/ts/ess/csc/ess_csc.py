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

__all__ = ["EssCsc", "command_ess_csc", "run_ess_csc"]

import asyncio
import traceback
import types
from collections.abc import Sequence

import jsonschema
from lsst.ts import salobj, utils
from lsst.ts.ess import common
from lsst.ts.xml.enums.ESS import ErrorCode

from . import __version__
from .config_schema import CONFIG_SCHEMA


def get_task_index_exception(
    tasks: Sequence[asyncio.Future],
) -> tuple[int | None, BaseException | None]:
    """Return (index, exception) of the first task with an exception.

    Parameters
    ----------
    tasks : `list` [`asyncio.Future`]
        A list of tasks.

    Returns
    -------
    info : `tuple`
        Return (index, exception) of the first task with an exception.
        Return (None, None) if no tasks have an exception.
    """
    for index, task in enumerate(tasks):
        if task.done() and not task.cancelled() and task.exception() is not None:
            return index, task.exception()
    return None, None


def run_ess_csc() -> None:
    asyncio.run(EssCsc.amain(index=True))


def command_ess_csc() -> None:
    asyncio.run(salobj.CscCommander.amain(name="ESS", index=True))


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
    override : `str`, optional
        Configuration override file to apply if ``initial_state`` is
        `State.DISABLED` or `State.ENABLED`.
    """

    enable_cmdline_state = True
    valid_simulation_modes = (0, 1)
    version = __version__

    def __init__(
        self,
        index: int,
        config_dir: str | None = None,
        initial_state: salobj.State = salobj.State.STANDBY,
        simulation_mode: int = 0,
        override: str = "",
        name: str = "ESS",
        config_schema: dict = CONFIG_SCHEMA,
    ) -> None:
        self.config: types.SimpleNamespace | None = None
        self.data_clients: list[common.data_client.BaseDataClient] = list()
        self.start_data_clients_task = utils.make_done_future()
        self.run_data_clients_task = utils.make_done_future()
        self.stop_data_clients_tasks: list[asyncio.Task] = []

        super().__init__(
            name=name,
            index=index,
            config_schema=config_schema,
            config_dir=config_dir,
            initial_state=initial_state,
            simulation_mode=simulation_mode,
            override=override,
        )

    async def begin_enable(self, data: salobj.BaseDdsDataType) -> None:
        """Begin do_enable; called before state changes.

        This override sends a CMD_INPROGRESS signal.

        Parameters
        ----------
        data : `salobj.BaseDdsDataType`
            Command data

        """
        await super().begin_enable(data)
        await self.cmd_enable.ack_in_progress(data, timeout=60)

    async def handle_summary_state(self) -> None:
        if self.summary_state == salobj.State.ENABLED:
            await self.start_data_clients()
        else:
            await self.stop_data_clients()

    async def start_data_clients(self) -> None:
        """Start the data clients."""
        # TODO DM-46349 Remove this as soon as the next XML after 22.1 is
        #  released.
        for client in self.data_clients:
            if isinstance(client, common.data_client.SnmpDataClient) and not hasattr(
                self, "tel_netbooter"
            ):
                raise RuntimeError(
                    "SnmpDataClient is not supported in this XML version."
                )

        tasks = [asyncio.create_task(client.start()) for client in self.data_clients]
        try:
            self.start_data_clients_task = asyncio.gather(*tasks)
            await self.start_data_clients_task
            self.run_data_clients_task = asyncio.create_task(self.run_data_clients())
        except Exception as main_exception:
            index, task_exception = get_task_index_exception(tasks)
            traceback_arg = None
            if index is None:
                code = ErrorCode.StartFailed
                report = (
                    "start failed but no start task failed; "
                    f"please report as a bug: {main_exception}"
                )
                traceback_arg = traceback.format_exc()
            else:
                client = self.data_clients[index]
                if any(
                    isinstance(task_exception, etype)
                    for etype in (ConnectionError, asyncio.IncompleteReadError, OSError)
                ):
                    code = ErrorCode.ConnectionFailed
                    report = f"{client} could not connect to its data server: {task_exception}"
                elif isinstance(task_exception, asyncio.TimeoutError):
                    code = ErrorCode.ConnectionFailed
                    report = f"{client} could not connect to its data server in time"
                else:
                    code = ErrorCode.StartFailed
                    report = f"{client} failed to start: {task_exception!r}"
            await self.fault(code=code, report=report, traceback=traceback_arg)
            raise

    async def run_data_clients(self) -> None:
        """Run the data clients, to read and publish environmental data."""
        tasks = [client.run_task for client in self.data_clients]
        try:
            self.run_data_clients_task = asyncio.gather(*tasks)
            await self.run_data_clients_task
        except Exception as main_exception:
            self.log.exception(f"run_data_clients failed: {main_exception!r}")
            index, task_exception = get_task_index_exception(tasks)
            traceback_arg = None
            if index is None:
                code = ErrorCode.RunFailed
                report = (
                    "run_data_clients failed, but no run task failed; "
                    f"please report as a bug: {main_exception}"
                )
                traceback_arg = traceback.format_exc()
            else:
                client = self.data_clients[index]
                if any(
                    isinstance(task_exception, etype)
                    for etype in (ConnectionError, asyncio.IncompleteReadError)
                ):
                    code = ErrorCode.ConnectionLost
                    report = (
                        f"{client} lost connection to its data server: {task_exception}"
                    )
                elif isinstance(task_exception, asyncio.TimeoutError):
                    code = ErrorCode.ConnectionLost
                    report = f"{client} timed out waiting for data"
                else:
                    code = ErrorCode.RunFailed
                    report = f"{client} failed while running: {task_exception!r}"
            await self.fault(code=code, report=report, traceback=traceback_arg)
            raise

    async def stop_data_clients(self) -> None:
        """Stop the data clients."""
        self.start_data_clients_task.cancel()
        self.run_data_clients_task.cancel()
        for task in self.stop_data_clients_tasks:
            task.cancel()

        self.stop_data_clients_tasks = [
            asyncio.create_task(client.stop()) for client in self.data_clients
        ]
        await asyncio.gather(*self.stop_data_clients_tasks, return_exceptions=True)
        failed_task_strs = [
            str(client)
            for client, task in zip(self.data_clients, self.stop_data_clients_tasks)
            if task.done() and not task.cancelled() and task.exception() is not None
        ]
        if failed_task_strs:
            failed_summary = ", ".join(failed_task_strs)
            self.log.warning(
                f"Failed to stop one or more data clients: {failed_summary}; continuing"
            )

    async def close_tasks(self) -> None:
        await super().close_tasks()
        await self.stop_data_clients()

    async def configure(self, config: types.SimpleNamespace) -> None:
        """Configure the CSC.

        Also store the device configurations for easier access when receiving
        and processing telemetry.

        Parameters
        ----------
        config : `types.SimpleNamespace`
            The configuration as described by the schema at
            `lsst.ts.ess.csc.CONFIG_SCHEMA`, as a struct-like object.
        """
        self.data_clients = list()
        for instance in config.instances:
            if instance["sal_index"] == self.salinfo.index:
                break
        else:
            raise RuntimeError(f"No config found for sal_index={self.salinfo.index}")
        for client_index, client_data in enumerate(instance["data_clients"]):
            client_class = common.data_client.get_data_client_class(
                client_data["client_class"]
            )
            config_schema = client_class.get_config_schema()
            validator = salobj.DefaultingValidator(config_schema)
            client_config_dict = client_data["config"]
            client_config_dict = validator.validate(client_config_dict)
            if not isinstance(client_config_dict, dict):
                raise RuntimeError(
                    f"config for data_clients[{client_index}] class {client_class} invalid: not a dict"
                )
            client_config = types.SimpleNamespace(**client_config_dict)
            try:
                client = client_class(
                    config=client_config,
                    topics=self,
                    log=self.log,
                    simulation_mode=self.simulation_mode,
                )
            except jsonschema.ValidationError as e:
                raise RuntimeError(
                    f"config for data_clients[{client_index}] class {client_class} invalid: {e}"
                )
            except Exception as e:
                raise RuntimeError(
                    f"Could not construct data_clients[{client_index}] class {client_class}: {e}"
                )
            self.data_clients.append(client)

    @staticmethod
    def get_config_pkg() -> str:
        return "ts_config_ocs"
