.. py:currentmodule:: lsst.ts.ess.csc

.. _lsst.ts.ess.csc-version_history:

###############
Version History
###############

v0.9.1
======

* Modernize pre-commit config versions.
* Introduce a mechanism to recover from communication failures instead of going to FAULT immediately.

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
