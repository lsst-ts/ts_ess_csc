.. py:currentmodule:: lsst.ts.ess.csc

.. _lsst.ts.ess.csc-rpi_protocol:

##########################
RPi Communication Protocol
##########################

This page describes the communication protocol used by the Raspberry Pi 4 servers.
This is the protocol used by `RPiDataClient`.

All communication is done via JSON encoded strings.
All JSON strings have a common header, indicated by the ``msg_type`` keyword.
The ``msg_type`` keyword can have the values

- command, indicating a command
- response, indicating a response to a command
- telemetry, indicating telemetry sent by the Raspberry Pi 4's

This keyword is needed to be able to distinguish between responses and telemetry in a fail safe manner.

Commands
--------

Apart from the ``msg_type`` keyword with the ``command`` value, all commands have the following keywords:

* cmd_name: the name of the command
* cmd_id: a unique, increasing long value determined by the CSC.
  This is the UNIX timestamp in milliseconds when the command was sent
* parameters: a set of name/value pairs where each name represents the name of a parameter and each value represents the value of the parameter

Note: only the ``configure`` command sends a non-emtpy parameter set.

Examples
^^^^^^^^

The start command looks as follows:

.. code-block:: js

  {
    "msg_type": "command",
    "cmd_name": "start",
    "cmd_id": 1,
    "parameters": {}
  }

The configure command for, for instance, two sensors looks as follows:

.. code-block:: js

  {
    "msg_type": "command",
    "cmd_name": "configure",
    "cmd_id": 23,
    "parameters": {
        "devices": [
            {
                "name": "Test01",
                "num_channels": 4,
                "dev_type": "FTDI",
                "dev_id": "ABC",
                "sens_type": "Temperature"
            },
            {
                "name": "Test02",
                "num_channels": 2,
                "dev_type": "Serial",
                "dev_id": "port_1",
                "sens_type": "Wind"
            }
        ]
    }
  }

Responses
---------

Apart from the ``msg_type`` keyword with the ``response`` value, all responses have the following keywords:

* cmd_id: the unique, increasing id of the command that the response is sent for
* cmd_status: can be

    * ack: in case the received command has been accepted
      It is assumed that ``ack`` only gets sent if and when the command has been executed successfully since for this CSC no long running commands have been implemented.
    * command_failed: the received command syntatically was correct but the execution failed
    * unknown_command: in case the received command in unknown
    * bad_parameter: in case an unknow parameter was received, or a parameter is missing, or there are too many parameters

Examples
^^^^^^^^

An ack command response looks as follows:

.. code-block:: js

  {
    "msg_type": "response",
    "cmd_id": 1,
    "cmd_status": "ack"
  }

Telemetry
---------

Apart from the ``msg_type`` keyword with the ``telemetry`` value, all telemetry messages have the following keywords:

* telemetry: a sensor specific string representing the telemetry.

Examples
^^^^^^^^

A telemetry message looks as follows:

.. code-block:: js

  {
    "msg_type": "telemetry",
    "telemetry": "['Test01', 1624900703.949579, 0, 24.0131, 18.5856, 19.5273, 21.4308]"
  }

which, in this case, means:

* The temperature sensor name (see the configuration example above)
* The UNIX timestamp of the measurement
* The temperatures were measured OK
* The four measured temperatures
