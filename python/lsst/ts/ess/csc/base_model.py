from __future__ import annotations

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

__all__ = ["BaseModel", "get_model_class", "register_model_class"]

import abc
import asyncio
import logging
import types
from typing import Any, Dict

from lsst.ts import salobj
from lsst.ts import utils

# Dict of model class name: model class.
# Access via the register_model_class and get_model_class functions.
_ModelClassRegistry: Dict[str:BaseModel] = dict()


def register_model_class(model_class: BaseModel) -> None:
    """Register a model class."""
    global _ModelClassRegistry
    name = model_class.__name__
    if name in _ModelClassRegistry:
        raise ValueError(f"model_class {name} already registered")
    if not issubclass(model_class, BaseModel):
        raise TypeError(f"model_class={model_class!r} is not an instance of BaseModel")
    _ModelClassRegistry[name] = model_class


def get_model_class(name: str) -> BaseModel:
    """Get a model class by class name."""
    global _ModelClassRegistry
    return _ModelClassRegistry[name]


class BaseModel(abc.ABC):
    """Base class for reading and publishing environmental data.

    Parameters
    ----------
    name : str
    config : types.SimpleNamespace
        The configuration, after validation by the schema returned
        by `get_config_schema` and conversion to a types.SimpleNamespace.
    topics : `salobj.Controller`
        The telemetry topics this model can write, as a struct with attributes
        such as ``tel_temperature``.
    log : `logging.Logger`
        Logger.
    simulation_mode : `int`, optional
        Simulation mode; 0 for normal operation.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        topics: salobj.Controller,
        log: logging.Logger,
        simulation_mode: int = 0,
    ) -> None:
        self.topics = topics
        self.connect_task = utils.make_done_future()
        self.run_task = utils.make_done_future()
        self.disconnect_task = utils.make_done_future()
        self.configure(config)
        self.log = log.getChild(str(self))
        self.simulation_mode = simulation_mode

    @classmethod
    @abc.abstractmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get the config schema as jsonschema dict."""
        raise NotImplementedError()

    @abc.abstractmethod
    def configure(self, config: types.SimpleNamespace) -> None:
        """Configure the model. Called once during construction."""
        raise NotImplementedError()

    @abc.abstractmethod
    def descr(self) -> str:
        """Return a brief description, without the class name.

        This will always be called after configure.

        This should be just enough information to distinguish
        one instance of this model from another.
        For example RPiModel should return something like::

           f"host={host}, port={port}"
        """
        raise NotImplementedError()

    @abc.abstractmethod
    async def connect(self) -> None:
        """Connect to the remote server.

        This should not be called if already connected.
        if that happens you may raise an exception.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the remote server.

        This must always be safe to call.
        It will be called while connected and while disconnected.
        """
        raise NotImplementedError()

    async def start(self) -> None:
        """Call disconnect, connect, and start the run task."""
        self.connect_task.cancel()
        self.disconnect_task.cancel()
        await self.disconnect()
        await self.connect()
        self.run_task = asyncio.create_task(self.run())

    @abc.abstractmethod
    async def run(self) -> None:
        """Read and publish data.

        Stop reading first, if reading.
        """
        raise NotImplementedError()

    async def stop(self) -> None:
        """Stop reading and publishing data.

        This is alway safe to call.
        """
        self.run_task.cancel()
        await self.disconnect()

    def __repr__(self) -> str:
        """Return a repr of this model.

        Subclasses may wish to override to add more information,
        such as host and port.
        """
        return f"{type(self).__name__}({self.descr()})"
