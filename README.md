# Isochrones

[![CI](https://github.com/EPFL-ENAC/isochrones/actions/workflows/ci.yml/badge.svg)](https://github.com/EPFL-ENAC/isochrones/actions/workflows/ci.yml)

_Package to generate isochrones using OpenTripPlanner_

# 🐇 Quick start

## Requirements

- A running [OpenTripPlanner](https://www.opentripplanner.org/) server, version 1.5, with an associated graph.

See the project [LASUR OTP](https://github.com/EPFL-ENAC/lasur-otp) to build and run a local OTP server.

## Installation

Development version:

```bash
uv pip install -e .
```

Stable version:

```bash
uv pip install git+https://github.com/EPFL-ENAC/isochrones.git@TAG
```

# Usage

```python
from isochrones import calculate_isochrones, intersect_isochrones, get_osm_features
```
