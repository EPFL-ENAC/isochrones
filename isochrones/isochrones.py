import datetime
from typing import Dict, List, Union
import requests
import geopandas as gpd


def calculate_isochrones(
    lat: float,
    lon: float,
    cutoffSec: list[int],
    date_time: datetime.datetime,
    otp_url: str,
    api_key: str = None,
    router: str = "default",
) -> gpd.GeoDataFrame:
    """
    Calculate isochrones for a given location and time.

    Args:
        lat (float): Latitude of the location.
        lon (float): Longitude of the location.
        cutoffSec (list[int]): List of cutoff times in seconds.
        date_time (datetime.datetime): The date and time for the isochrone calculation.
        otp_url (str): The base URL of the OTP server.
        api_key (str, optional): The API key for authentication.
        router (str, optional): The router ID to use for the request, defaulting to "default".

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

    # create the url by combining the base OTP url, and router
    url = f"{otp_url}/otp/routers/{router}/isochrone"

    headers = {"x-api-key": api_key} if api_key is not None else None
    r = requests.get(url, params=payload, headers=headers)

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
