#!/usr/bin/env python
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

import asyncio
import logging

from lsst.ts import salobj

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG,
)


async def main():
    domain = salobj.Domain()
    ess = salobj.Remote(domain=domain, name="ESS")
    logging.info(dir(ess))

    logging.info("Calling start_task")
    await ess.start_task
    logging.info("Calling cmd_start.set_start")
    await ess.cmd_start.set_start(timeout=20)
    logging.info("Calling set_summary_state")
    await salobj.set_summary_state(remote=ess, state=salobj.State.ENABLED)

    data = await ess.tel_temperature4Ch.next(flush=True)
    logging.info(
        f"temp: {data.temperatureC01} {data.temperatureC02} {data.temperatureC03} " f"{data.temperatureC04}"
    )
    logging.info("Calling set_summary_state")
    await salobj.set_summary_state(remote=ess, state=salobj.State.DISABLED)
    logging.info("Calling set_summary_state")
    await salobj.set_summary_state(remote=ess, state=salobj.State.STANDBY)
    logging.info("Calling set_summary_state")
    await salobj.set_summary_state(remote=ess, state=salobj.State.OFFLINE)


if __name__ == "__main__":
    logging.info("main")
    loop = asyncio.get_event_loop()
    try:
        logging.info("Calling main method")
        loop.run_until_complete(main())
    except Exception:
        logging.exception("Excdeption!")
        pass
