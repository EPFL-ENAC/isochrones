import os
import re
import osmnx
from typing import Dict, Optional
import geopandas as gpd
import pyogrio
import pandas as pd


def get_osm_features(
    bounding_box: tuple[float, float, float, float],
    tags: Dict[str, bool],
    crs: str = "EPSG:3857",
    osm_pbf_path: Optional[str] = None,
) -> gpd.GeoDataFrame:
    """
    Get OSM features within a bounding box.

    This function retrieves OpenStreetMap (OSM) features based on the specified
    tags and bounding box. The retrieved features are returned as a GeoDataFrame
    in long format, with one row per feature. For line, polygons and
    multipolygons, the geometries are represented as their centroid.

    Args:
        bounding_box (tuple): A tuple of (west, south, east, north) coordinates.
        tags (Dict[str, bool] or Dict[str, list/str/None]): A dictionary of OSM tags to filter features.
            Values can be:
               - True: accept any value for that key
               - list/tuple/set: accept only listed values
               - str/int: accept that exact value
               - None: key existence is enough
        crs (str): The coordinate reference system for the output GeoDataFrame.
        osm_pbf_path (str, optional): Path to a local .osm.pbf file. If provided and exists,
            pyosmium-based BBoxFeatureHandler will be used. Otherwise falls back to osmnx.

    Returns:
        gpd.GeoDataFrame: A GeoDataFrame containing the OSM features within the
        bounding box.
    """

    # Validate bounding box length
    if not (isinstance(bounding_box, (tuple, list)) and len(bounding_box) == 4):
        raise ValueError(
            "bounding_box must be a tuple or list of exactly 4 elements: (west, south, east, north)"
        )

    # If a local OSM PBF is provided and exists, use the pyosmium handler
    if osm_pbf_path and os.path.exists(osm_pbf_path):
        gdf = pyogrio.read_dataframe(
            osm_pbf_path,
            layer="points",
            bbox=bounding_box,  
        )
        gdf["tags"] = gdf["other_tags"].apply(parse_osm_tags)
        for col in ["amenity", "healthcare", "shop", "tourism", "office", "public_transport"]:
            gdf[col] = gdf["tags"].apply(lambda d: d.get(col))
            
        # filter rows based on tags
        def row_matches_tags(row, tags):
            # Check if a row matches one of the specified tags
            for key, value in tags.items():
                tag_value = row.get(key)
                if value is True:
                    if tag_value is not None:
                        return True 
                elif isinstance(value, (list, tuple, set)):
                    if tag_value in value:
                        return True
                else:
                    if tag_value == value:
                        return True
            return False
        gdf = gdf[gdf.apply(lambda row: row_matches_tags(row, tags), axis=1)]
        
    else:
        # Fallback to osmnx.features.features_from_bbox when no pbf given
        # osmnx.features_from_bbox expects (north, south, east, west) in some versions;
        # keep using original call signature from before.
        # Note: osmnx.features.features_from_bbox may return geometries in WGS84 by default.
        gdf = osmnx.features.features_from_bbox(bounding_box, tags)

        # ensure columns lower-case for tag keys
        # osmnx returns columns for tags already; we'll normalize column names
        gdf.columns = [c.lower() if isinstance(c, str) else c for c in gdf.columns]

        # add osm_type/osm_id if missing (osmnx index holds them in some versions)
        if "osm_type" not in gdf.columns or "osm_id" not in gdf.columns:
            try:
                gdf["osm_type"] = gdf.index.map(lambda x: x[0])  # Get 'node' or 'way'
                gdf["osm_id"] = gdf.index.map(lambda x: x[1])
            except Exception:
                gdf["osm_type"] = None
                gdf["osm_id"] = None

    # Normalize tag columns and reshape to long format (one row per tag key)
    id_names = ["osm_type", "osm_id", "geometry"]
    tag_names_requested = [k.lower() for k in tags.keys()]

    existing_tag_cols = [c for c in tag_names_requested if c in gdf.columns]
    # If none of the requested tag columns exist (handler may have stored them differently), try to pick any tag-like columns
    if not existing_tag_cols:
        # treat all non-id, non-geometry columns as tag columns
        existing_tag_cols = [c for c in gdf.columns if c not in id_names]

    # ensure columns for id_names exist
    for col in id_names:
        if col not in gdf.columns:
            gdf[col] = None

    # Convert to requested CRS and reduce geometry to centroid for non-point geometries
    # First reproject
    try:
        gdf = gdf.to_crs(crs)
    except Exception:
        # If gdf is already in the desired crs or reprojection fails, ignore
        pass

    # Convert polygons/lines to centroids
    gdf["geometry"] = gdf.geometry.representative_point()

    # Melt to long format for requested/existing tag columns
    gdf_long = gdf.melt(id_vars=id_names, value_vars=existing_tag_cols, var_name="variable", value_name="value")
    gdf_long = gdf_long[gdf_long["value"].notna()].reset_index(drop=True)

    return gdf_long

def parse_osm_tags(tag_str):
    if pd.isna(tag_str) or tag_str == "":
        return {}
    d = {}
    # Split by comma, then split by =>
    # handle quoted strings
    for kv in re.findall(r'"([^"]+)"=>"(.*?)"', tag_str):
        key, value = kv
        d[key] = value
    return d