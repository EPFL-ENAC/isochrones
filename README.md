# Isochrones
_Package to generate isochrones using OpenTripPlanner_

# 🐇 Quick start

## Requirements

- [uv](https://docs.astral.sh/uv/) Python package and project manager
- [git](https://git-scm.com/) version control system
- [Docker](https://www.docker.com/) container platform


## Installation

Isochrones relies on [uv](https://docs.astral.sh/uv/) to manage Python virtual environments. You need to install it first if you don't already have it. Refer to the official [uv documentation](https://docs.astral.sh/uv/getting-started/installation/).

Then, run the following command to install Isochrones:
```bash
uv tool install isochrones
```


## Docker

To run the Docker container, you can use the provided `Dockerfile`. Build the image with:
```bash
docker build -t your-image-name .
```

Then, run the container with the following command, specifying the location of the subfolder containing the graph data:

```bash
docker run -p 8080:8080 -v /path/to/your/graphs:/opt/otp/graphs your-image-name
```
