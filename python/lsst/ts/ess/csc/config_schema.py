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

__all__ = ["CONFIG_SCHEMA"]

import yaml

CONFIG_SCHEMA = yaml.safe_load(
    """
$schema: http://json-schema.org/draft-07/schema#
$id: https://github.com/lsst-ts/ts_ess/blob/master/python/lsst/ts/ess/csc/config_schema.py
# title must end with one or more spaces followed by the schema version, which must begin with "v"
title: ESS v1
description: Schema for ESS configuration files
type: object
properties:
  host:
    description: IP address of the TCP/IP interface
    type: string
    format: hostname
    default: "127.0.0.1"
  port:
    description: Port number of the TCP/IP interface
    type: integer
    default: 5000
  devices:
    type: array
    default:
    - name: EssTemperature4Ch
      sensor_type: Temperature
      channels: 4
      device_type: FTDI
      ftdi_id: AL05OBVR
    items:
      type: object
      properties:
        name:
          description: Name of the sensor
          type: string
        sensor_type:
          description: Type of the sensor
          type: string
          enum:
          - HX85A
          - HX85BA
          - Temperature
          - Wind
        channels:
          description: Number of channels
          type: integer
        device_type:
          description: Type of the device
          type: string
          enum:
          - FTDI
          - Serial
      anyOf:
      - if:
          properties:
            device_type:
              const: FTDI
        then:
          properties:
            ftdi_id:
              description: FTDI Serial ID to connect to.
              type: string
      - if:
          properties:
            device_type:
              const: Serial
        then:
          properties:
            serial_port:
              description: Serial port to connect to.
              type: string
"""
)