import datetime
from typing import Dict, List, Union, Optional
import requests
import geopandas as gpd


def calculate_isochrones(
    lat: float,
    lon: float,
    cutoffSec: list[int],
    date_time: datetime.datetime,
    mode: str,
    otp_url: str,
    api_key: Optional[str] = None,
    bike_speed: float = 13.0,
    router: str = "default",
    crs: str = "EPSG:4326",
    overlap: bool = True,
) -> gpd.GeoDataFrame:
    """
    Calculate isochrones for a given location and time. The isochrones returned are non-overlapping polygons
    representing areas reachable within specified cutoff times.

    Args:
        lat (float): Latitude of the location.
        lon (float): Longitude of the location.
        cutoffSec (list[int]): List of cutoff times in seconds.
        date_time (datetime.datetime): The date and time for the isochrone calculation. This is considered to be the time of departure (arriveBy = False)
        mode (str): The travel mode (e.g., "WALK", "BICYCLE", "TRANSIT"). Will be checked against available modes from the OTP server.
        If the mode is not available, a ValueError will be raised.
        otp_url (str): The base URL of the OTP server.
        api_key (str, optional): The API key for authentication.
        bike_speed (float): The bike speed in km/h, only relevant if mode is "BICYCLE".
        router (str, optional): The router ID to use for the request, defaulting to "default".
        crs (str, optional): The coordinate reference system for the output GeoDataFrame, defaulting to "EPSG:4326".
        overlap (bool, optional): Whether to return overlapping isochrones or non-overlapping ones. Defaults to True.

    Returns:
        gpd.GeoDataFrame: A GeoDataFrame containing the isochrones.
    """
    coordinates = f"{lat},{lon}"
    date = date_time.strftime("%m-%d-%Y")  # Format as MM-DD-YYYY
    time = date_time.strftime("%I:%M%p")  # Format as HH:MM pm/am

    # check that mode is in the keys of the available modes
    available_modes = get_available_modes(otp_url, router, api_key)
    if mode not in available_modes.keys():
        raise ValueError(
            f"Mode '{mode}' is not available. Available modes are: {list(available_modes.keys())}"
        )

    payload: Dict[str, Union[str, List[str], bool, float]] = {
        "fromPlace": coordinates,
        "toPlace": coordinates,
        "date": date,
        "time": time,
        "cutoffSec": [str(sec) for sec in cutoffSec],
        "mode": available_modes[mode],
        "arriveBy": False,
    }

    # Only include bikeSpeed if mode is BICYCLE
    if mode.upper() == "BICYCLE":
        payload["bikeSpeed"] = bike_speed / 3.6

    # create the url by combining the base OTP url, and router
    url = f"{otp_url}/otp/routers/{router}/isochrone"

    headers = {"x-api-key": api_key} if api_key is not None else None
    r = requests.get(url, params=payload, headers=headers)

    if r.status_code != 200:
        raise RuntimeError(f"Failed to retrieve isochrones: {r.status_code} - {r.text}")

    isochrone = gpd.GeoDataFrame.from_features(r.json()["features"])
    isochrone.crs = crs

    if not overlap and len(cutoffSec) > 1:
        # Sort by time to ensure correct order for difference calculation
        isochrone = isochrone.sort_values("time").reset_index(drop=True)
        # Iterate from the largest isochrone down to the second smallest
        for i in range(len(isochrone) - 1, 0, -1):
            # Subtract the smaller isochrone from the larger one
            isochrone.at[i, "geometry"] = isochrone.loc[i, "geometry"].difference(
                isochrone.loc[i - 1, "geometry"]
            )

    return isochrone


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


def get_available_modes(
    otp_url: str, router: str = "default", api_key: Optional[str] = None
) -> Dict[str, str]:
    """
    Get available travel modes from the OTP server.

    Args:
        otp_url (str): The base URL of the OTP server.
        router (str, optional): The router ID to use for the request, defaulting to "default".
        api_key (str, optional): The API key for authentication.

    Returns:
        Dict[str, str]: A dictionary of available travel modes.
    """
    url = f"{otp_url}/otp/routers/{router}"
    headers = {"x-api-key": api_key} if api_key is not None else None

    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        raise RuntimeError(
            f"Failed to retrieve available modes: {r.status_code} - {r.text}"
        )

    travel_options = r.json()["travelOptions"]
    return {item["name"]: item["value"] for item in travel_options}
