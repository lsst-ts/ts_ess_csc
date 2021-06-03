# This file is part of ts_ess.
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
$id: https://github.com/lsst-ts/ts_ess/blob/master/python/lsst/ts/ess/config_schema.py
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
    default: [{"name": "EssTemperature4Ch"}]
    items:
      type: object
      properties:
        name:
          description: Name of the sensor
          type: string
          default: EssTemperature4Ch
        channels:
          description: Number of channels
          type: integer
          default: 4
        type:
          description: Type of the device
          type: string
          enum:
          - FTDI
          - Serial
          default: FTDI
      anyOf:
      - if:
          properties:
            type:
              const: FTDI
        then:
          properties:
            ftdi_id:
              description: FTDI Serial ID to connect to.
              type: string
              default: "AL05OBVR"
      - if:
          properties:
            type:
              const: Serial
        then:
          properties:
            serial_port:
              description: Serial port to connect to.
              type: string
              default: "serial_ch_1"
"""
)
