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
$id: https://github.com/lsst-ts/ts_ess/blob/main/python/lsst/ts/ess/csc/config_schema.py
# title must end with one or more spaces followed by the schema version, which must begin with "v"
title: ESS v5
description: Schema for ESS configuration.
type: object
properties:
  instances:
    type: array
    description: Configuration for each ESS instance.
    minItem: 1
    items:
      type: object
      properties:
        sal_index:
          type: integer
          description: SAL index of ESS instance.
          minimum: 1
        data_clients:
          description: Configuration for each data client run by this instance.
          type: array
          minItems: 1
          items:
            type: object
            properties:
              client_class:
                description: Data client class name, e.g. RPiDataClient.
                type: string
              config:
                description: Configuration for the data client.
                type: object
            required:
              - client_class
              - config
            additionalProperties: false
      required:
        - sal_index
        - data_clients
      additionalProperties: false
required:
  - instances
additionalProperties: false
"""
)
