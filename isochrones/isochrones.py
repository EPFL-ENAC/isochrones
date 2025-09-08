import datetime
from typing import Dict, List, Union
import requests
import geopandas as gpd


def calculate_isochrones(
    lat: float,
    lon: float,
    cutoffSec: list[int],
    date_time: datetime.datetime,
    ssl: bool,
    hostname: str,
    port: int,
    router: str,
) -> gpd.GeoDataFrame:
    """
    Calculate isochrones for a given location and time.

    Args:
        lat (float): Latitude of the location.
        lon (float): Longitude of the location.
        cutoffSec (list[int]): List of cutoff times in seconds.
        date_time (datetime.datetime): The date and time for the isochrone calculation.
        ssl (bool): Whether to use SSL for the request.
        hostname (str): The hostname of the OTP server.
        port (int): The port of the OTP server.
        router (str): The router ID to use for the request.

    Returns:
        gpd.GeoDataFrame: A GeoDataFrame containing the isochrones.
    """
    coordinates = f"{lat},{lon}"
    date = date_time.strftime("%m-%d-%Y")  # Format as MM-DD-YYYY
    time = date_time.strftime("%I:%M%p")  # Format as HH:MM pm/am

    payload: Dict[str, Union[str, List[str]]] = {
        "fromPlace": coordinates,
        "toPlace": coordinates,
        "date": date,
        "time": time,
        "cutoffSec": [str(sec) for sec in cutoffSec],
    }

    # create the url by combining the hostname, port, and router
    url = f"{'https' if ssl else 'http'}://{hostname}:{port}/otp/routers/{router}/isochrone"

    r = requests.get(url, params=payload)

    if r.status_code != 200:
        raise RuntimeError(f"Failed to retrieve isochrones: {r.status_code} - {r.text}")

    return gpd.GeoDataFrame.from_features(r.json()["features"])


def intersect_isochrones(
    isochrones: gpd.GeoDataFrame, points: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """
    Intersect isochrones with geographical points of interest.

    Args:
        isochrones (gpd.GeoDataFrame): The isochrones GeoDataFrame.
        points (gpd.GeoDataFrame): The random points GeoDataFrame.

    Returns:
        gpd.GeoDataFrame: The intersected GeoDataFrame.
    """
    return gpd.overlay(points, isochrones, how="intersection")
