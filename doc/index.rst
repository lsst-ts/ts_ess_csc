.. py:currentmodule:: lsst.ts.ess.csc

.. _lsst.ts.ess.csc:

###############
lsst.ts.ess.csc
###############

.. image:: https://img.shields.io/badge/Project Metadata-gray.svg
    :target: https://ts-xml.lsst.io/index.html#index-master-csc-table-ess
.. image:: https://img.shields.io/badge/SAL\ Interface-gray.svg
    :target: https://ts-xml.lsst.io/sal_interfaces/ESS.html
.. image:: https://img.shields.io/badge/GitHub-gray.svg
    :target: https://github.com/lsst-ts/ts_ess_csc
.. image:: https://img.shields.io/badge/Jira-gray.svg
    :target: https://jira.lsstcorp.org/issues/?jql=labels+%3D+ts_ess_csc

Overview
========

The ESS Commandable SAL Component (CSC) reads various environmental sensors at the Vera C. Rubin Observatory, and publishes the resulting data in ESS telemetry topics.
There will be at least one, and likely several, ESS CSC(s) running at Rubin Observatory.

.. _lsst.ts.ess.csc-user_guide:

User Guide
==========

To run the ESS CSC::

    run_ess_csc.py sal_index

Each ``sal_index`` you specify must have a matching entry in the configuration you specify in the ``start`` command, else the command will fail.

This command-line script supports ``--help``.

Configuration
-------------

Configuration files are stored in `ts_config_ocs`_.

There should be one standard configuration file for each site.
Each configuration file specifies configuration for all ESS SAL indices supported at that site.
To run all ESS CSCs appropriate for a site, examine the configuration file and run one ESS CSC for each entry in it.

The ESS CSC uses "data clients" to communicate with environmental data servers and publish the telemetry, in order to flexibly handle different kinds of servers.
Each data client class has its own configuration schema.

A CSC configuration file primarily contains of a list of sal_index: configuration for a data client.

There is presently one data client: `RPiDataClient`.
More are planned, including a LabJack data client in ``ts_ess_labjack``.

.. _ts_config_ocs: https://github.com/lsst-ts/ts_config_ocs

.. _lsst.ts.ess.csc-developer_guide:

Developer Guide
===============

Data clients do most of the work for the CSC: reading and publishing environmental data.
The CSC constructs the clients specified in the config file and runs them.

This package defines one data client: `RPiDataClient`, which uses TCP/IP to communicate with Raspberry Pi 4 data servers.
The environmental sensors are connected to the Raspberry Pi 4 servers, and the servers are scattered around the observatory.
The Raspberry Pi 4 servers use code from `ts_ess_controller`_.

The protocol used to communicate with Raspberry Pi 4 servers is described in :doc:`rpi_protocol`:

.. toctree::
   :maxdepth: 2

   rpi_protocol.rst

This package and `ts_ess_controller`_ share common code in `ts_ess_common`_.

.. _ts_ess_controller: https://ts-ess-controller.lsst.io
.. _ts_ess_common: https://ts-ess-common.lsst.io

.. _lsst.ts.ess.csc-api_reference:

Python API reference
--------------------

.. automodapi:: lsst.ts.ess.csc
   :no-main-docstr:

.. _lsst.ts.ess.csc-contributing:

Contributing
------------

``lsst.ts.ess.csc`` is developed at https://github.com/lsst-ts/ts_ess_csc.
You can find Jira issues for this module using `labels=ts_ess_csc <https://jira.lsstcorp.org/issues/?jql=project%3DDM%20AND%20labels%3Dts_ess_csc>`_.

Version History
===============

.. toctree::
    version_history
    :maxdepth: 1
