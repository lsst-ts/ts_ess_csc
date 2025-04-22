.. py:currentmodule:: lsst.ts.ess.csc

.. _lsst.ts.ess.csc-version_history:

###############
Version History
###############

v0.19.2 (2025-04-22)
====================

New Features
------------

- Switched to towncrier. (`DM-50329 <https://rubinobs.atlassian.net//browse/DM-50329>`_)
- Avoided `asyncio_default_fixture_loop_scope` pytest warning. (`DM-50329 <https://rubinobs.atlassian.net//browse/DM-50329>`_)


Bug Fixes
---------

- Fixed failing unit test. (`DM-50329 <https://rubinobs.atlassian.net//browse/DM-50329>`_)
- Fixed package version file generation. (`DM-50329 <https://rubinobs.atlassian.net//browse/DM-50329>`_)


.. towncrier release notes start

v0.19.1
========

* Remove ts_idl dependency from conda recipe and add ts_xml.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 22.2
* ts_ess_common 0.20
* ts_tcpip 2
* ts_utils 1

v0.19.0
========

* Incorporate code for electrical power management and other SNMP operations.
* Cleanup and fix conda recipe.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 22.2
* ts_ess_common 0.20
* ts_tcpip 2
* ts_utils 1

v0.18.10
========

* Update SiglentSSA3000xSpectrumAnalyzerDataClient to allow configuring the start and end scan frequency.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 20
* ts_ess_common 0.17
* ts_tcpip 2
* ts_utils 1.0

v0.18.9
=======

* Update CSC bin script for running the CSC locally.
* Improve Young weather station code readability.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 20
* ts_ess_common 0.17
* ts_tcpip 2
* ts_utils 1.0

v0.18.8
=======

* Remove WeatherStation rain rate jump check.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 20
* ts_ess_common 0.17
* ts_tcpip 2
* ts_utils 1.0

v0.18.7
=======

* Make sure that the TcpipDataClient test runs in simulation mode.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 20
* ts_ess_common 0.17
* ts_tcpip 2
* ts_utils 1.0

v0.18.6
=======

* Revert renaming of ESS Common SocketServer class.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 20
* ts_ess_common 0.17
* ts_tcpip 2
* ts_utils 1.0

v0.18.5
=======

* Allow subclassing of the ESS CSC class.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 20
* ts_ess_common 0.17
* ts_tcpip 2
* ts_utils 1.0

v0.18.4
=======

* Add a unit test for the TcpipDataClient.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 20
* ts_ess_common 0.17
* ts_tcpip 2
* ts_utils 1.0

v0.18.3
=======

* Fix the conda recipe.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 20
* ts_ess_common 0.17
* ts_tcpip 2
* ts_utils 1.0

v0.18.2
=======

* Update the version of ts-conda-build to 0.4 in the conda recipe.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 20
* ts_ess_common 0.17
* ts_tcpip 2
* ts_utils 1.0

v0.18.1
=======

* Increase config version.
* Consolidate Lightning and RPi data clients into one class.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 20
* ts_ess_common 0.17
* ts_tcpip 2
* ts_utils 1.0

v0.18.0
=======

* Import enums from ts_xml instead of ts_idl.
* Separate connection code from sensor reading code.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 20
* ts_ess_common 0.17
* ts_tcpip 2
* ts_utils 1.0

v0.17.1
=======

* Convert HX85BA barometric pressure to Pa using astropy units.
* Convert weather station barometric pressure to Pa using the correct scale factor.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 20
* ts_ess_common 0.16
* ts_tcpip 1.1
* ts_utils 1.0

v0.17.0
=======

* Rename telemetry items for which the topic has the same name.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 20
* ts_ess_common 0.16
* ts_tcpip 1.1
* ts_utils 1.0

v0.16.10
========

* Fix reconnection issue in Young weather station DataClient.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 16
* ts_ess_common 0.16
* ts_tcpip 1.1
* ts_utils 1.0

v0.16.9
=======

* Prepare unit tests for Kafka.
* Make the Young weather station DataClient automatically reconnect when a timeout happens.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 16
* ts_ess_common 0.16
* ts_tcpip 1.1
* ts_utils 1.0

v0.16.8
=======

* Make sure that MockSiglentSSA3000xDataServer reads a command before sending data to avoid filling up of the write buffer.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 16
* ts_ess_common 0.16
* ts_tcpip 1.1
* ts_utils 1.0

v0.16.7
=======

* Correct some log messages that contained the wrong host and port.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 16
* ts_ess_common 0.16
* ts_tcpip 1.1
* ts_utils 1.0

v0.16.6
=======

* Move some documentation to ts_ess_common.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 16
* ts_ess_common 0.16
* ts_tcpip 1.1
* ts_utils 1.0

v0.16.5
=======

* Use ts_tcpip OneClientReadLoopServer.
  This requires ts_tcpip 1.1.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 16
* ts_ess_common 0.16
* ts_tcpip 1.1
* ts_utils 1.0

v0.16.4
=======

* Remove XML 15 compatibility:

  * For the ``lightningStrikeStatus`` telemetry topic, initialize ``closeStrikeRate`` and ``totalStrikeRate`` to NaN instead of -1.
  * For the ``lightningStrike`` event, report "no lightning strikes nearby" by setting ``correctedDistance`` and  ``uncorrectedDistance`` to infinity, instead of -1.
  * Stop rounding these fields and other lightning-related numbers to integer; all are now float.

* Remove scons support.
* Git hide egg info and simplify .gitignore.
* Further refinements for ts_pre_commit_config:

  * Remove unused bits from ``conda/meta.yaml``.
  * Remove ``setup.cfg``.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 16
* ts_ess_common 0.14
* ts_tcpip
* ts_utils 1.0

v0.16.3
=======

* `get_circular_mean_and_std_dev`: fix a possible exception in computing direction statistics.
* `Young32400WeatherStationDataClient`: improve error handling in the ``handle_data`` method.
* `AirFlowAccumulator`: add missing documentation for the ``log`` constructor argument.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 15
* ts_ess_common 0.14
* ts_tcpip
* ts_utils 1.0

v0.16.2
=======

* Remove backward compatibility with XML 15.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 16
* ts_ess_common 0.14
* ts_tcpip
* ts_utils 1.0

v0.16.1
=======

* Make the unit tests compatible with XML 15.0.
* Make handling of lightning strike telemetry compatible with XML 15.0.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 15
* ts_ess_common 0.14
* ts_tcpip
* ts_utils 1.0

v0.16.0
=======

* Remove unused options for pytest.
* Switch Young32400WeatherStationDataClient to BaseReadLoopDataClient.
* Switch SiglentSSA3000xSpectrumAnalyzerDataClient to BaseReadLoopDataClient.
* Switch ControllerDataClient to BaseReadLoopDataClient.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 16
* ts_ess_common 0.14
* ts_tcpip
* ts_utils 1.0

v0.15.1
=======

* CONFIG_SCHEMA: update to version v5, for changes to lsst.ts.ess.labjack.LabJackAccelerometerDataClient.
  Note: that data client requires ts_xml 16.
* Use ts_pre_commit_conf.
* ``Jenkinsfile``: use the shared library.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 16
* ts_ess_common 0.11
* ts_tcpip
* ts_utils 1.0

v0.15.0
=======

* Bug fix: reported airFlow direction and directionStdDev did not handle wraparound correctly.
  Use circular statistics instead of standard statistics.
* `AirFlowAccumulator`: add a ``log`` attribute, making it more like `AirTurbulenceAccumulator`.
* Add `get_circular_mean_and_std_dev` function.
* Add `Young32400WeatherStationDataClient`.
* Add `SiglentSSA3000xSpectrumAnalyzerDataClient`.
  This requires ts_xml 16.
* Add location to lightning sensors telemetry.
* Improve type annotation of get_median_and_std_dev.
* Add command_ess_csc entry point.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 16 (14 is OK if not using SiglentSSA3000xSpectrumAnalyzerDataClient)
* ts_ess_common 0.11
* ts_tcpip
* ts_utils 1.0

v0.14.2
=======

* Remove cast to int for lightning strike bearing and wind direction standard deviation.
* Add a unit test function to check Windsonic telemetry because the one in ts_ess_common is invalid for the telemetry.
* Clean up pyproject.toml dependencies.
* Remove `pip install` step since the dependencies were added to ts-develop.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 14
* ts_ess_common 0.11
* ts_tcpip
* ts_utils 1.0

v0.14.1
=======

* Fix NaN to int conversion in Windsonic anemometer telemetry handling.
* Fix invalid config schema for lightning sensors.
* Decrease safe_interval default value because it clashed with communication timeout value.
* Add check for number of elements in timestamp list in ElectricFieldStrengthAccumulator class.
* Improve logging of lightning sensors telemetry handling.
* Temporarily cast lightning strike bearing to int until ts_xml has been updated.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 14
* ts_ess_common 0.11
* ts_tcpip
* ts_utils 1.0

v0.14.0
=======

* Fix the unit of wind speed in the doc strings of AirTurbulenceAccumulator.
* Add support for the Gill Windsonic 2-d anemometer.
* Move all accumulators to a sub-module.
* Move all data clients to a sub-module.
* Refactor the run_ess_csc entry point.
* Use quartiles to compute estimated standard deviation.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 14
* ts_ess_common 0.11
* ts_tcpip
* ts_utils 1.0

v0.13.2
=======

* Update type annotations for newer MyPy.
* Add debug statements.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 14
* ts_ess_common 0.10
* ts_tcpip
* ts_utils 1.0

v0.13.1
=======

* pre-commit: update mypy version.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 14
* ts_ess_common 0.10
* ts_tcpip
* ts_utils 1.0

v0.13.0
=======

* Update for ts_xml 14, which is required.
* Switch from py.test to pytest.
* Improve the way medians are computed.
* Extract base class for data clients connecting to an ESS Controller.
* Add a data client (and support classes) for processing electric field and lightning telemetry.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 14
* ts_ess_common 0.10
* ts_tcpip
* ts_utils 1.0

v0.12.0
=======

* Update for ts_xml 13, which is required.
* Modernize type annotations.
* Add class `AirTurbulenceAccumulator`.
* Fix reconnection issue.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 13
* ts_ess_common 0.9.3
* ts_tcpip
* ts_utils 1.0

v0.11.2
=======

* Modernize airTurbulence telemetry.
  This was potentially compatible with ts_xml 12.1 but there will be no such release.
  This version is not compatible with ts_xml 13.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 12.
* ts_ess_common 0.9.3
* ts_tcpip
* ts_utils 1.0

v0.11.1
=======

* Restore pytest config.
* Fix CSAT3B baud rate.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 11
* ts_ess_common 0.8
* ts_tcpip
* ts_utils 1.0

v0.11.0
=======

* Add support for multiple Python versions for conda.
* Sort imports with isort.
* Install new pre-commit hooks.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 11
* ts_ess_common 0.8
* ts_tcpip
* ts_utils 1.0

v0.10.0
=======

* Add baud_rate configuration key.
* Add support for the Campbell Scientific CSAT3B 3D anemometer.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 11
* ts_ess_common 0.8
* ts_tcpip
* ts_utils 1.0

v0.9.1
======

* Modernize pre-commit config versions.
* Introduce a mechanism to recover from communication failures instead of going to FAULT immediately.
* Switch to pyproject.toml.
* Use entry_points instead of bin scripts.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 11
* ts_ess_common 0.7
* ts_tcpip
* ts_utils 1.0

v0.9.0
======

* Use ErrorCode enum from ts_idl, which requires ts_idl 3.7.
* ``setup.cfg``: set asyncio_mode = auto.
* git ignore .hypothesis.

Requires:

* ts_salobj 7
* ts_idl 3.7
* IDL file for ESS from ts_xml 11
* ts_ess_common 0.7
* ts_tcpip
* ts_utils 1.0

v0.8.0
======

* Update for ts_salobj 7 and ts_xml 11, both of which are required.

Requires:

* ts_salobj 7
* ts_idl 3.7 strongly recommended, but 3.5 or 3.6 will do
* IDL file for ESS from ts_xml 11
* ts_ess_common 0.7
* ts_tcpip
* ts_utils 1.0


v0.7.0
======

* Update unit tests for ts_salobj 6.8.
  This change requires ts_salobj 6.8.
* Modify to use data clients (subclasses of `lsst.ts.ess.common.BaseDataClient`) to communicate with data servers.
  This requires ts_ess_common 0.7.
* Use new error codes from ts_idl 3.7, which is recommended but not required, due to a temporary local version of the ErrorCode enum class.
  All clients of this CSC should use ts_idl v3.7.0 in order to get correct ErrorCode values.
* Rename the conda package from ts-ess to ts-ess-csc.
* Fix API docs.
* Enable mypy type checking.
* Change ``master`` to ``main`` in CONFIG_SCHEMA's ``id``, in preparation for renaming the branch.
* Remove START and STOP commands from RPi Data Client.
* The sensor name, timestamp, response code and data are encoded as separate named entities.

Requires:

* ts_salobj 6.8
* ts_idl 3.7 strongly recommended, but 3.5 or 3.6 will do
* IDL file for ESS from ts_xml 10.1
* ts_ess_common 0.7
* ts_tcpip
* ts_utils 1.0


v0.6.1
======

* Fixed import for ESS Common MockTestTools.

Requires:

* ts_salobj 6.3
* ts_idl 3.1
* IDL file for ESS from ts_xml 10.1
* ts_ess_common
* ts_tcpip
* ts_utils 1.0


v0.6.0
======

* Consolidated all multi-channel temperature topics into one.
* Replaced the use of ts_salobj functions with ts_utils functions.
* Added tests for all supported devices in the test class for the CSC.
* Removed logging configuration from CSC run script.
* Added telemetry for the computed dew point in all humidity sensors that don't provide it themselves.
* Made sure that the CSC goes into FAULT state in case of an error.
* Added location to the configuration of the devices.
* Made sure that the CSC reports the sensor location in the telemetry.

Requires:

* ts_salobj 6.3
* ts_idl 3.1
* IDL file for ESS from ts_xml 10.1
* ts_ess_common
* ts_tcpip
* ts_utils 1.0


v0.5.1
======

* Fixed launch script to get index argument.
* Added auto-enable capability.

Requires:

* ts_salobj 6.6
* ts_idl 3.3
* IDL file for ESS from ts_xml 10.0
* ts_ess_controller
* ts_ess_common
* ts_tcpip

v0.5.0
======

* Removed all sensor code.
* Added a description of the communication protocol.
* Added support for the Omega HX85A and HX85BA humidity sensors.
* Added rudimentary exception handling in case a sensor encounters an error.
* Renamed the project to ts_ess_csc.
* Made sure to refer to the ts_ess_common and ts_ess_controller Python packages.

Requires:

* ts_salobj 6.3
* ts_idl 3.1
* IDL file for ESS from ts_xml 9.1
* ts_ess_controller
* ts_ess_common
* ts_tcpip


v0.4.1
======

* Fixed code errors to make the CSC work on the summit.

Requires:

* ts_salobj 6.3
* ts_idl 3.1
* IDL file for ESS from ts_xml 9.1
* ts_envsensors
* ts_tcpip


v0.4.0
======

* Code reworked to be able to work locally and remotely.
  When working remotely, a running socket server from ts_envsensors is required.
* Removed ``pytest-runner`` and ``tests_require``.
* Added support for multiple sensors.
* Added handling of configuration errors.

Requires:

* ts_salobj 6.3
* ts_idl 3.1
* IDL file for ESS from ts_xml 9.1
* ts_envsensors
* ts_tcpip


v0.3.0
======

Code reworked to use asyncio properly.

Requires:

* ts_salobj 6.3
* ts_idl 3.1
* IDL file for ESS from ts_xml 8.0


v0.2.0
======

The sensors code, and with that the CSC, was completely rewitten.
Black version upgraded to 20.8b1
ts-conda-build version upgraded to 0.3

Requires:

* ts_salobj 6.3
* ts_idl 3.1
* IDL file for ESS from ts_xml 8.0


v0.1.0
======

First release of the Environmental Sensors Suite CSC.

This version already includes many useful things:

* A functioning ESS CSC which can connect to a multi-channel temperature sensor.
* Support for USB and FTDI sensors.

Requires:

* ts_salobj 6.3
* ts_idl
* IDL file for ESS from ts_xml 7.0
