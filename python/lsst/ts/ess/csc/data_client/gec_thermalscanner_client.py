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

import asyncio
import logging
import random
import socket
import time
import types
from copy import deepcopy
from math import ceil
from typing import Any

import yaml
from lsst.ts import salobj, tcpip
from lsst.ts.ess import common
from lsst.ts.utils import make_done_future

NUM_THERMOCOUPLES = 95


class GecThermalscannerClient(common.data_client.BaseReadLoopDataClient):
    """Retrieve temperatutes from the GEC Instruments thermal scanner."""

    def __init__(
        self,
        config: types.SimpleNamespace,
        topics: salobj.Controller | types.SimpleNamespace,
        log: logging.Logger,
        simulation_mode: int = 0,
    ):
        super().__init__(
            config=config,
            topics=topics,
            log=log,
            simulation_mode=simulation_mode,
            auto_reconnect=True,
        )

        self.simulation_interval = 2
        self.simulation_mode = simulation_mode
        self.mock_data_task = make_done_future()

        self.write_topics = []

        num_topics = ceil(NUM_THERMOCOUPLES / 16)
        for tn in range(num_topics):
            topic = deepcopy(self.topics.tel_temperature)
            num_channels = (
                16 - (num_topics * 16 - NUM_THERMOCOUPLES)
                if tn == (num_topics - 1)
                else 16
            )
            topic.tel_temperature.set(
                sensorName=f"{self.config.sensor_name} {tn + 1}/{num_topics}",
                location=self.config.location,
                numChannels=num_channels,
            )
            self.write_topics.append(topic)

        self.mock_data_server: MockGetThermalscannerDataServer | None = None

        self.client: tcpip.Client | None = None

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        return yaml.safe_load(
            """
$schema: http://json-schema.org/draft-07/schema#
description: Schema for GecThermalscannerClient
type: object
properties:
  host:
    description: IP address of the Windows machine running the PinPoint TCP/IP interface.
    type: string
    format: hostname
  port:
    description: Port number of the PinPoint TCP/IP interface.
    type: integer
    default: 4447
  connect_timeout:
    description: Timeout for connecting to the GEC Instruments Thermal Scanner (sec).
    type: number
  read_timeout:
    description: >-
      Timeout for reading data from the weather station (sec). Note that the standard
      output rate is either 2 Hz or 15 Hz, depending on configuration.
    type: number
  max_read_timeouts:
    description: Maximum number of read timeouts before an exception is raised.
    type: integer
    default: 5
  location:
    description: Sensor location (used for the telemetry topic).
    type: string
required:
  - host
  - port
  - connect_timeout
  - read_timeout
  - max_read_timeouts
  - location
"""
        )

    @property
    def connected(self) -> bool:
        return self.client is not None and self.client.connected

    async def connect(self) -> None:
        if self.connected:
            await self.disconnect()

        if self.simulation_mode > 0:
            self.mock_data_server = MockGetThermalscannerDataServer(
                self.log, self.simulation_interval
            )
            self.mock_data_task.cancel()
            self.mock_data_task = asyncio.create_task(self.mock_data_server.run())

            host = tcpip.LOCALHOST_IPV4
            port = self.mock_data_server.port
        else:
            host = self.config.host
            port = self.config.port

        self.client = tcpip.Client(host=host, port=port, log=self.log)
        await asyncio.wait_for(self.client.start_task, self.config.connect_timeout)

    async def disconnect(self) -> None:
        self.mock_data_task.cancel()
        try:
            if self.connected:
                assert self.client is not None
                await self.client.close()
        finally:
            self.client = None
        if self.mock_data_server is not None:
            await self.mock_data_server.close()
            self.mock_data_server = None

    async def read_data(self) -> None:
        """Read data from thermal scanner."""
        assert self.client is not None
        read_bytes = await asyncio.wait_for(
            self.client.readuntil(tcpip.DEFAULT_TERMINATOR),
            timeout=self.config.read_timeout,
        )
        data = read_bytes.decode()
        if not data:
            return
        timestamp, temps = data.split(":")
        temperatures = temps.split(",")
        if len(temperatures) != NUM_THERMOCOUPLES:
            self.log.error(
                "invalid data - expected %d values, received %d: %s",
                NUM_THERMOCOUPLES,
                len(temperatures),
                data,
            )
            return

        timestamp = float(timestamp)

        for tn, topic in enumerate(self.write_topics):
            await topic.set_write(
                timestamp=timestamp,
                temperatureItem=temperatures[tn * 16 : (tn + 1) * 16],
            )


class MockGetThermalscannerDataServer:

    def __init__(self, log: logging.Logger, simulation_interval: float):
        self.log = log
        self.simulation_interval = simulation_interval
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(("", 0))
        self.port = self.socket.getsockname()[1]

    async def run(self) -> None:
        self.socket.listen(1)

        while True:
            connection, client_address = self.socket.accept()
            try:
                self.log.info(
                    "Simulator: Client connected, client address is %s", client_address
                )
                while True:
                    temperatures = [
                        str(random.randint(-1000, 1000) / 100.0)
                        for i in range(NUM_THERMOCOUPLES)
                    ]

                    connection.sendall(
                        bytes(
                            str(time.time()) + ":" + ",".join(temperatures) + "\n",
                            "ascii",
                        )
                    )
                    await asyncio.sleep(self.simulation_interval)
            finally:
                self.log.info(
                    "Simulator: Client connection from %s closed.", client_address
                )
                connection.close()

    async def close(self) -> None:
        self.socket.close()
