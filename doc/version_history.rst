.. py:currentmodule:: lsst.ts.ess

.. _lsst.ts.ess.version_history:

###############
Version History
###############

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
