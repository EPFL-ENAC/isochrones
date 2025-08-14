import datetime
from typing import Dict, List, Union
import requests
import geopandas as gpd


def calculate_isochrones(
    lat: float, lon: float, cutoffSec: list[int], date_time: datetime.datetime
):
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

    r = requests.get("http://localhost:8080/otp/routers/main/isochrone", params=payload)

    if r.status_code != 200:
        raise RuntimeError(f"Failed to retrieve isochrones: {r.status_code}")

    return gpd.GeoDataFrame.from_features(r.json()["features"])
