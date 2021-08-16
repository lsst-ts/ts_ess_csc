.. py:currentmodule:: lsst.ts.ess.csc

.. _lsst.ts.ess.csc:

###############
lsst.ts.ess.csc
###############

``ts_ess_csc`` is a Commandable SAL Component (CSC) to control various environmental sensors at the Vera C. Rubin Observatory.
There will be at least one, and likely several, CSC(s) running at Rubin Observatory.
The CSC makes a socket connection to several Raspberry Pi 4's, to which the actual sensors ar connected, distributed around the observatory.
The Raspberry Pi 4's then use the code from `ts_ess_sensors`_ to retrieve the sensor telemetry from the sensors and to convert the telemetry to a common format.
The two projects share common code in `ts_ess_common` _.
The telemetry then is sent to the CSC which publishes it as SAL topics.
The protocol used for commands for controlling the ``ts_ess_controller`` code and for transferring the telemetry is described in :doc:`Communication Protocols <protocols>`.

.. _ts_ess_controller: https://ts-ess_controller.lsst.io
.. _ts_ess_common: https://ts-ess_common.lsst.io

.. _lsst.ts.ess-using:

Using lsst.ts.ess
=================

.. toctree linking to topics related to using the module's APIs.

.. toctree::
    protocols
    :maxdepth: 1

.. _lsst.ts.ess-contributing:

Contributing
============

``lsst.ts.ess`` is developed at https://github.com/lsst-ts/ts_ess_csc.
You can find Jira issues for this module using `labels=ts_ess_csc <https://jira.lsstcorp.org/issues/?jql=project%3DDM%20AND%20labels%3Dts_ess_csc>`_.

Python API reference
====================

.. automodapi:: lsst.ts.ess
   :no-main-docstr:

Version History
===============

.. toctree::
    version_history
    :maxdepth: 1
