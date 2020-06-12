import asynctest

from lsst.ts import salobj
from lsst.ts import ess


class CscTestCase(salobj.BaseCscTestCase, asynctest.TestCase):
    def basic_make_csc(self, initial_state, config_dir, simulation_mode, **kwargs):
        return ess.EssCsc(
            initial_state=initial_state,
            config_dir=config_dir,
            simulation_mode=simulation_mode,
        )

    async def test_standard_state_transitions(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.check_standard_state_transitions(enabled_commands=(),)

    async def test_bin_script(self):
        await self.check_bin_script(name="ESS", index=None, exe_name="run_ess.py")
