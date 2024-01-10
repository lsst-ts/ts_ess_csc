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

import collections
import contextlib
import types
import unittest

import numpy as np
import pytest
from lsst.ts import salobj, utils
from lsst.ts.ess import csc


class SiglentSSA3000xDataClientTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        # Prepare for Kafka.
        if hasattr(salobj, "set_random_topic_subname"):
            salobj.set_random_topic_subname()
        else:
            salobj.set_random_lsst_dds_partition_prefix()
        config_schema = (
            csc.SiglentSSA3000xSpectrumAnalyzerDataClient.get_config_schema()
        )
        validator = salobj.DefaultingValidator(config_schema)
        config_dict = dict(
            host="localhost",
            port=5000,
            connect_timeout=5,
            read_timeout=1,
            location="Test Location",
            sensor_name="MockSSA3000X",
            poll_interval=0.1,
        )
        config_dict = validator.validate(config_dict)
        self.config = types.SimpleNamespace(**config_dict)

    @contextlib.asynccontextmanager
    async def create_controller(self) -> collections.abc.AsyncGenerator:
        """Create an ESS Controller and Remote and wait for them to start."""
        index_generator = utils.index_generator()
        index = next(index_generator)
        async with salobj.Controller(
            name="ESS", index=index
        ) as self.controller, salobj.Remote(
            domain=self.controller.domain, name="ESS", index=index, readonly=True  # type: ignore
        ) as self.remote:
            yield

    def create_data_client(self) -> csc.SiglentSSA3000xSpectrumAnalyzerDataClient:
        """Helper function to create a DataClient.

        Returns
        -------
        csc.SiglentSSA3000xSpectrumAnalyzerDataClient:
            The DataClient.
        """
        data_client = csc.SiglentSSA3000xSpectrumAnalyzerDataClient(
            config=self.config,
            topics=self.controller,
            log=self.controller.log,
            simulation_mode=1,
        )
        return data_client

    async def test_siglent_ssa3000x_spectrum_analyzer_data_client(self) -> None:
        async with self.create_controller():
            data_client = self.create_data_client()

            await data_client.start()
            try:
                telemetry = await self.remote.tel_spectrumAnalyzer.next(flush=False)
                assert telemetry.startFrequency == pytest.approx(
                    csc.SiglentSSA3000xSpectrumAnalyzerDataClient.start_frequency
                )
                assert telemetry.stopFrequency == pytest.approx(
                    csc.SiglentSSA3000xSpectrumAnalyzerDataClient.stop_frequency
                )
                assert np.amax(telemetry.spectrum) <= 0.0
                assert np.amin(telemetry.spectrum) >= -100.0
            finally:
                await data_client.stop()
