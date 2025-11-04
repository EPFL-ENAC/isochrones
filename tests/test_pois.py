import os
import sys
import pytest
from isochrones import get_osm_features

bbox = (6.13, 46.19, 6.15, 46.21)
tags = {"amenity": ["school", "hospital"]}
#tags = {"public_transport": True}
#tags = {"shop": True}
crs = "EPSG:4326"
    
def test_get_osm_features_from_local_pbf():
    osmData = os.path.join(os.path.dirname(__file__), "..", ".data", "geneva-greater-area-all.osm.pbf")
    
    # Check osm data file exists
    if not os.path.exists(osmData):
        pytest.skip(f"Test OSM PBF data file is missing: {osmData}")

    gdf = get_osm_features(
        bounding_box=bbox,
        osm_pbf_path=osmData if os.path.exists(osmData) else None,
        tags=tags,
        crs=crs,
    )
    print(gdf, file=sys.stdout)

def test_get_osm_features_from_package_pbf():
    gdf = get_osm_features(
        bounding_box=bbox,
        osm_pbf_path="geneva-greater-area.osm.pbf",
        tags=tags,
        crs=crs,
    )
    print(gdf, file=sys.stdout)
    
# def test_get_osm_features_from_overpass():
#     gdf = get_osm_features(
#         bounding_box=bbox,
#         osm_pbf_path=None,
#         tags=tags,
#         crs=crs,
#     )
#     print(gdf, file=sys.stdout)