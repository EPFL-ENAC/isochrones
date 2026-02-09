import datetime
import logging
from typing import Dict, List, Union, Optional
import requests
import geopandas as gpd
import shapely
from shapely.geometry import MultiPolygon, Polygon

logger = logging.getLogger(__name__)


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
    area_threshold: float = 1e-6,
) -> gpd.GeoDataFrame:
    """
    Calculate isochrones for a given location and time.

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
        overlap (bool, optional): Whether to return overlapping isochrones or non-overlapping ones. If the calculation of non-overlapping
        isochrones fails, overlapping isochrones will be returned instead. Defaults to True.
        area_threshold (float, optional): Minimum area threshold to filter out small polygons within the isochrones, expressed in the area units of the
        specified CRS (e.g. degrees squared for EPSG:4326). Defaults to 1e-6.
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

    isochrone["geometry"] = isochrone["geometry"].buffer(0)

    isochrone["geometry"] = isochrone["geometry"].map(
        lambda geom: filter_small_polygons(geom, area_threshold)
    )

    if not overlap:
        try:
            isochrone = make_non_overlapping(isochrone)
        except shapely.errors.GEOSException as e:
            logger.warning(
                f"Failed to make isochrones non-overlapping: {type(e).__name__}: {str(e)}. "
                "Returning overlapping isochrones instead."
            )
            # Return original overlapping isochrone

    return isochrone


def filter_small_polygons(
    geom: Union[MultiPolygon, Polygon, None], min_area: float
) -> Union[MultiPolygon, Polygon]:
    """
    Filter out small polygons from a MultiPolygon geometry based on an area threshold.

    Args:
        geom (Union[MultiPolygon, Polygon, None]): The geometry to filter.
        min_area (float): The minimum area threshold.

    Returns:
        Union[MultiPolygon, Polygon, None]: The filtered geometry.
    """
    if geom is None:
        return Polygon()  # Return an empty polygon if geometry is None
    if isinstance(geom, MultiPolygon):
        # Only filter out if there is more than one polygon
        if len(geom.geoms) == 1:
            return geom
        filtered = [p for p in geom.geoms if p.area >= min_area]
        if not filtered:
            return Polygon()
        return MultiPolygon(filtered)

    return geom


def make_non_overlapping(isochrone: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Make isochrones non-overlapping by subtracting smaller availability zones from larger ones.

    This function implements a dual-level error handling approach:
    - Level 1: Attempts direct geometry difference operations
    - Level 2: If direct difference fails, splits the smaller geometry into individual polygons
      and attempts to subtract them one by one, skipping any problematic polygons

    Args:
        isochrone (gpd.GeoDataFrame): The isochrones GeoDataFrame.

    Returns:
        gpd.GeoDataFrame: The non-overlapping isochrones.
    """
    if len(isochrone) <= 1:
        return isochrone

    # Sort by time to ensure correct order for difference calculation
    isochrone = isochrone.sort_values("time").reset_index(drop=True)

    # Iterate from the largest isochrone down to the second smallest
    for i in range(len(isochrone) - 1, 0, -1):
        try:
            # Level 1: Attempt direct difference operation
            isochrone.at[i, "geometry"] = isochrone.loc[i, "geometry"].difference(
                isochrone.loc[i - 1, "geometry"]
            )
        except shapely.errors.GEOSException as e:
            # Level 2: Polygon-level recovery
            # The problematic geometry is usually the smaller_geom being subtracted
            logger.warning(
                f"Geometry difference failed for isochrone at index {i} (time={isochrone.loc[i, 'time']}): "
                f"{type(e).__name__}: {str(e)}. Attempting polygon-level recovery."
            )

            larger_geom = isochrone.loc[i, "geometry"]
            smaller_geom = isochrone.loc[i - 1, "geometry"]

            # Extract individual polygons from the SMALLER geometry (the one being subtracted)
            if isinstance(smaller_geom, MultiPolygon):
                smaller_polygons = list(smaller_geom.geoms)
            elif isinstance(smaller_geom, Polygon):
                smaller_polygons = [smaller_geom]
            else:
                logger.warning(
                    f"Unexpected smaller geometry type at index {i - 1}: {type(smaller_geom)}. "
                    "Skipping difference, keeping original larger geometry."
                )
                continue  # Keep the larger_geom as-is

            # Start with the original larger geometry
            result_geom = larger_geom

            # Iteratively subtract each polygon from smaller_geom
            for poly_idx, small_poly in enumerate(smaller_polygons):
                try:
                    result_geom = result_geom.difference(small_poly)
                except Exception as poly_e:
                    logger.warning(
                        f"Failed to subtract polygon {poly_idx} from smaller geometry at index {i - 1}: "
                        f"{type(poly_e).__name__}: {str(poly_e)}. Skipping this polygon."
                    )
                    # Skip this problematic polygon, continue with others
                    continue

            # Update the geometry with the result
            isochrone.at[i, "geometry"] = result_geom

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
