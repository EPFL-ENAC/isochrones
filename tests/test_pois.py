import os
import sys
import pytest
from isochrones import get_osm_features
import importlib.metadata as md

def test_version_metadata_present():

    osmData = os.path.join(os.path.dirname(__file__), "..", "data", "switzerland-251102.osm.pbf")
    
    print(osmData, file=sys.stderr)
    
    # Check osm data file exists
    if not os.path.exists(osmData):
        pytest.skip("Test OSM PBF data file is missing.")
        
    
    gdf = get_osm_features(
        bounding_box=(6.5, 46.5, 6.6, 46.6),
        osm_pbf_path=osmData,
        tags={"amenity": ["school", "hospital"]},
        crs="EPSG:2056",
    )

    print(gdf, file=sys.stderr)