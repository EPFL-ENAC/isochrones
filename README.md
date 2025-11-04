# Isochrones

[![CI](https://github.com/EPFL-ENAC/isochrones/actions/workflows/ci.yml/badge.svg)](https://github.com/EPFL-ENAC/isochrones/actions/workflows/ci.yml)

_Package to generate isochrones using OpenTripPlanner_

# 🐇 Quick start

## Requirements

- A running [OpenTripPlanner](https://www.opentripplanner.org/) server, version 1.5, with an associated graph.

See the project [LASUR OTP](https://github.com/EPFL-ENAC/lasur-otp) to build and run a local OTP server.

## Installation

### Development version

```bash
uv pip install -e .
```

To install the dependencies required to run the example notebook, use

```bash
uv pip install -e .[example]
```

or

```bash
uv pip install -e '.[example]'
```

if you are on macOS.

### Stable version:

```bash
# Replace TAG with the desired version or tag, e.g. v1.2.3
uv pip install git+https://github.com/EPFL-ENAC/isochrones.git@v1.2.3
# or
uv pip install git+https://github.com/EPFL-ENAC/isochrones.git@TAG
```

# Run tests

```bash
uv pip install -e .[dev]
uv run pytest -q
```

# Usage

```python
from isochrones import calculate_isochrones, intersect_isochrones, get_osm_features
```

# Development

Generate Geneva OSM PBF file:

```bash
make pbf pbf-geneva
```