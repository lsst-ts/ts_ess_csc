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

__all__ = ["SiglentSSA3000xSpectrumAnalyzerDataClient"]

import asyncio
import logging
import types
from typing import Any

import numpy as np
import yaml
from lsst.ts import salobj, tcpip, utils
from lsst.ts.ess import common

# The standard TCP/IP line terminator (bytes).
TERMINATOR = b"\n"


class SiglentSSA3000xSpectrumAnalyzerDataClient(common.BaseDataClient):
    ###########################################################################
    # The following constants need to be hard coded because of limitations in #
    # the way DDS handles arrays. This ensures that all arrays always have    #
    # the same, fixed, length.                                                #
    ###########################################################################
    # The commands to use with the spectrum analyzer.
    query_trace_data_cmd = ":trace:data? 1"
    set_freq_start_cmd = ":frequency:start 0.0 GHz"
    set_freq_stop_cmd = ":frequency:stop 3.0 GHz"
    # The start and stop frequencies as float values.
    start_frequency = 0.0
    stop_frequency = 3.0e9
    # The number of data points as returned by the spectrum analyzer given the
    # fixed start and stop frequency.
    num_data_points = 751

    def __init__(
        self,
        config: types.SimpleNamespace,
        topics: salobj.Controller | types.SimpleNamespace,
        log: logging.Logger,
        simulation_mode: int = 0,
    ) -> None:
        super().__init__(
            config=config, topics=topics, log=log, simulation_mode=simulation_mode
        )

        self.topics.tel_spectrumAnalyzer.set(
            sensorName=self.config.sensor_name, location=self.config.location
        )

        # Lock for TCP/IP communication
        self.stream_lock = asyncio.Lock()

        self.client: tcpip.Client | None = None
        self.read_loop_task = utils.make_done_future()

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        return yaml.safe_load(
            """
$schema: http://json-schema.org/draft-07/schema#
description: Schema for SiglentSSA3000xSpectrumAnalyzerDataClient
type: object
properties:
  host:
    description: Hostname of the TCP/IP interface.
    type: string
    format: hostname
  port:
    description: Port number of the TCP/IP interface.
    type: integer
    default: 5000
  connect_timeout:
    description: Timeout for connecting to the spectrum analyzer (sec).
    type: number
  read_timeout:
    description: >-
      Timeout for reading data from the spectrum analyzer (sec). Note that the
      standard output rate is 1 Hz.
    type: number
  location:
    description: Sensor location (used for all telemetry topics).
    type: string
  sensor_name:
    description: Spectrum Analyzer name.
    type: string
    default: SSA3000X
  poll_interval:
    description: The poll interval between requests for the scan telemetry (sec).
    type: number
    default: 1.0
required:
  - host
  - port
  - connect_timeout
  - read_timeout
  - location
  - sensor_name
  - poll_interval
additionalProperties: false
"""
        )

    def descr(self) -> str:
        return f"host={self.config.host}, port={self.config.port}"

    @property
    def connected(self) -> bool:
        return self.client is not None and self.client.connected

    async def connect(self) -> None:
        await self.disconnect()

        if self.simulation_mode == 0:
            self.client = tcpip.Client(
                host=self.config.host, port=self.config.port, log=self.log
            )
            await asyncio.wait_for(self.client.start_task, self.config.connect_timeout)
        else:
            self.log.info(
                "Simulating output from an SSA3000X Spectrum Analyzer serial interface at "
                f"host={self.config.host}, port={self.config.port}"
            )

    async def disconnect(self) -> None:
        self.read_loop_task.cancel()
        try:
            if self.connected:
                assert self.client is not None  # make mypy happy
                await self.client.close()
        finally:
            self.client = None

    async def run(self) -> None:
        self.read_loop_task.cancel()
        self.read_loop_task = asyncio.create_task(self.read_loop())

    async def write(self, data: str) -> None:
        """Write the data appended with the standard terminator.

        Parameters
        ----------
        data : `str`
            The data to write.
        """
        assert self.client is not None  # make mypy happy
        await self.client.write(data.encode() + b"\r\n")

    async def read_loop(self) -> None:
        """Read raw data from the SSA3000X Spectrum Analyzer."""
        try:
            if self.connected and self.simulation_mode == 0:
                # Make sure that the correct frequency range is used by the
                # spectrum analyzer.
                await self.write(self.set_freq_start_cmd)
                await self.write(self.set_freq_stop_cmd)
            while self.connected or self.simulation_mode != 0:
                timestamp = utils.current_tai()
                if self.simulation_mode == 0:
                    await self.write(self.query_trace_data_cmd)
                    assert self.client is not None  # make mypy happy
                    read_bytes = await asyncio.wait_for(
                        self.client.readuntil(TERMINATOR),
                        timeout=self.config.read_timeout,
                    )
                    raw_data = read_bytes.decode().strip()
                    raw_data_items = raw_data.split(",")
                    data = [float(i.strip()) for i in raw_data_items]
                else:
                    # Generate random data between 0 and -100 dB. Convert to
                    # list to keep mypy happy.
                    data = (-100.0 * np.random.random(self.num_data_points)).tolist()
                try:
                    await self.topics.tel_spectrumAnalyzer.set_write(
                        startFrequency=self.start_frequency,
                        stopFrequency=self.stop_frequency,
                        spectrum=data,
                        timestamp=timestamp,
                    )
                except Exception as e:
                    self.log.exception(f"Failed to handle {data=}: {e!r}")

                # Maybe a bit of an overkill but this ensures that no drift
                # gets introduced while sleeping.
                sleep_delay = (
                    utils.current_tai() - timestamp - self.config.sleep_interval
                )
                if sleep_delay > 0:
                    await asyncio.sleep(sleep_delay)
        except Exception as e:
            self.log.exception(f"read loop failed: {e!r}")
            raise
