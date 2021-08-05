.. py:currentmodule:: lsst.ts.ess

.. _lsst.ts.ess:

###########
lsst.ts.ess
###########

``ts_ess`` is a Commandable SAL Component (CSC) to control various environmental sensors at the Vera C. Rubin Observatory.
There will be at least one, and likely several, CSC(s) running at Rubin Observatory.
The CSC makes a socket connection to several Raspberry Pi 4's, to which the actual sensors ar connected, distributed around the observatory.
The Raspberry Pi 4's then use the code from `ts_ess_sensors`_ to retrieve the sensor telemetry from the sensors and to convert the telemetry to a common format.
The telemetry then is sent to the CSC which sends it to the EFD.
The protocol used for commands for controlling the ``ts_ess_sensors`` code and well for transferring the telemetry is described in :doc:`Communication Protocols <protocols>`.

.. _ts_ess_sensors: https://ts-ess_sensors.lsst.io

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

``lsst.ts.ess`` is developed at https://github.com/lsst-ts/ts_ess.
You can find Jira issues for this module using `labels=ts_ess <https://jira.lsstcorp.org/issues/?jql=project%3DDM%20AND%20labels%3Dts_ess>`_.

Python API reference
====================

.. automodapi:: lsst.ts.ess
   :no-main-docstr:

Version History
===============

.. toctree::
    version_history
    :maxdepth: 1
