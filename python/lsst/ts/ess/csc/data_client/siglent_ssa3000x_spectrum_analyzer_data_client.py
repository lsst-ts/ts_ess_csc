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

# The expected number of data points as returned by the spectrum analyzer given
# the fixed start and stop frequency.
EXPECTED_NUMBER_OF_DATA_POINTS = 751

# The maximum allowed number of truncated messages. This is set to 1 so reading
# truncated data when connecting doesn't lead to a RuntimeError.
MAX_NUM_TRUNCATED_DATA = 1


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

        # TODO DM-38363 Remove this as soon as XML 16 has been released.
        if not hasattr(self.topics, "tel_spectrumAnalyzer"):
            raise RuntimeError("At least ts_xml 16.0 required to use this class.")

        self.topics.tel_spectrumAnalyzer.set(
            sensorName=self.config.sensor_name, location=self.config.location
        )

        # Lock for TCP/IP communication
        self.stream_lock = asyncio.Lock()

        self.client: tcpip.Client | None = None
        self.read_loop_task = utils.make_done_future()

        self.mock_data_server: MockSiglentSSA3000xDataServer | None = None

        self.number_of_truncated_data_read = 0

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
            host = self.config.host
            port = self.config.port
        else:
            self.log.info(
                "Simulating output from an SSA3000X Spectrum Analyzer serial interface at "
                f"host={self.config.host}, port={self.config.port}"
            )
            self.mock_data_server = MockSiglentSSA3000xDataServer(log=self.log)
            await self.mock_data_server.start_task
            host = tcpip.LOCALHOST_IPV4
            port = self.mock_data_server.port

        self.client = tcpip.Client(host=host, port=port, log=self.log)
        await asyncio.wait_for(self.client.start_task, self.config.connect_timeout)

    async def disconnect(self) -> None:
        self.read_loop_task.cancel()
        try:
            if self.connected:
                assert self.client is not None  # make mypy happy
                await self.client.close()
        finally:
            self.client = None
        if self.mock_data_server is not None:
            await self.mock_data_server.close()
            self.mock_data_server = None

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
            while self.connected:
                timestamp = utils.current_tai()
                await self.write(self.query_trace_data_cmd)
                assert self.client is not None  # make mypy happy
                read_bytes = await asyncio.wait_for(
                    self.client.readuntil(TERMINATOR),
                    timeout=self.config.read_timeout,
                )
                raw_data = read_bytes.decode().strip()
                raw_data_items = raw_data.split(",")
                data = [float(i.strip()) for i in raw_data_items]
                if (
                    len(data) < EXPECTED_NUMBER_OF_DATA_POINTS
                    and self.number_of_truncated_data_read < MAX_NUM_TRUNCATED_DATA
                ):
                    logging.warning(
                        f"Data of length {len(data)} read. Ignoring because this is "
                        f"read #{self.number_of_truncated_data_read} out of {MAX_NUM_TRUNCATED_DATA}."
                    )
                    self.number_of_truncated_data_read += 1
                elif len(data) != EXPECTED_NUMBER_OF_DATA_POINTS:
                    raise RuntimeError(
                        f"Encountered {len(data)} data points instead of "
                        f"{EXPECTED_NUMBER_OF_DATA_POINTS}. Check the Spectrum "
                        f"Analyzer and the configuration."
                    )
                else:
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
                    utils.current_tai() - timestamp - self.config.poll_interval
                )
                if sleep_delay > 0:
                    await asyncio.sleep(sleep_delay)
        except Exception as e:
            self.log.exception(f"read loop failed: {e!r}")
            raise


class MockSiglentSSA3000xDataServer(tcpip.OneClientServer):
    """Mock Siglent SSA3000x data server.

    Parameters
    ----------
    log : `logging.Logger`
        Logger.
    """

    def __init__(
        self,
        log: logging.Logger,
    ) -> None:
        super().__init__(
            host=tcpip.LOCALHOST_IPV4,
            port=0,
            log=log,
            connect_callback=self.connect_callback,
        )
        self.write_loop_task = utils.make_done_future()

    async def connect_callback(self, server: tcpip.OneClientServer) -> None:
        self.write_loop_task.cancel()
        if server.connected:
            self.write_loop_task = asyncio.create_task(self.write_loop())

    async def write_loop(self) -> None:
        try:
            while self.connected:
                rng = np.random.default_rng(10)
                data = -100.0 * rng.random(EXPECTED_NUMBER_OF_DATA_POINTS)
                data_string = ", ".join(f"{d:0.3f}" for d in data)
                await self.write(data_string.encode() + TERMINATOR)
        except Exception as e:
            self.log.exception(f"write loop failed: {e!r}")
