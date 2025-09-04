import osmnx
from typing import Dict
import geopandas as gpd


def get_osm_features(
    bounding_box: tuple[float, float, float, float],
    tags: Dict[str, bool],
    crs: str = "EPSG:3857",
) -> gpd.GeoDataFrame:
    # Get OSM features within the bounding box
    gdf = osmnx.features.features_from_bbox(bounding_box, tags)

    gdf["osm_type"] = gdf.index.map(lambda x: x[0])  # Get 'node' or 'way'
    gdf["osm_id"] = gdf.index.map(lambda x: x[1])

    id_names = ["osm_type", "osm_id", "geometry"]
    tag_names = list(map(lambda x: x.lower(), tags.keys()))

    # Reshape the GeoDataFrame to have one row per tag
    gdf = gdf.melt(id_vars=id_names, value_vars=tag_names)
    gdf = gdf[gdf["value"].notna()]
    gdf = gdf.to_crs(crs)

    gdf["geometry"] = gdf["geometry"].centroid

    return gdf
