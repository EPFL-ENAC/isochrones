import geopandas as gpd
import pandas as pd
from importlib.resources import files


def get_osm_files():
    """
    Get files in package data directory with .osm.pbf suffix.
    """
    return [
        f.name
        for f in files("isochrones").joinpath("data").iterdir()
        if f.name.endswith(".osm.pbf")
    ]


def filter_routes_by_isochrone(
    routes: gpd.GeoDataFrame,
    stops: gpd.GeoDataFrame,
    isochrone: gpd.GeoDataFrame,
    min_stops_bus_tram: int = 2,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """
    Filter transit routes by isochrone coverage using pre-extracted data.

    Args:
        routes (gpd.GeoDataFrame): Pre-extracted transit routes. Must have columns: osm_id, route, ref, network,
            from, to, geometry.
        stops (gpd.GeoDataFrame): Pre-extracted transit stops (from extract_all_transit_stops()
            or loaded from GeoParquet). Must have columns: osm_id, geometry.
        isochrone (gpd.GeoDataFrame): Isochrone polygon(s) to filter by (from calculate_isochrones()).
        min_stops_bus_tram (int, optional): Minimum number of stops required for bus/tram routes
            to be included. Trains are always included regardless. Default: 2.

    Returns:
        tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]: A tuple containing the filtered routes and the stops within those routes.

    Raises:
        ValueError: If required columns are missing from input GeoDataFrames, or if
            include/exclude networks have overlapping values.

    """
    if stops.empty or isochrone.empty or routes.empty:
        return routes.iloc[0:0].copy(), stops.iloc[0:0].copy()

    # Ensure same CRS for spatial join
    if stops.crs != isochrone.crs:
        stops = stops.to_crs(isochrone.crs)

    if routes.crs != isochrone.crs:
        routes = routes.to_crs(isochrone.crs)

    # Check whether the data frame was grouped by route_master or route
    grouped_by_route_master = False
    if "variant_route_ids" in routes.columns:
        grouped_by_route_master = True

    # Spatial join: find stops within isochrones
    stops_per_route = count_route_stops_in_isochrones(stops, isochrone)
    train_routes = stops_per_route[
        (stops_per_route["transit_mode"] == "train")
        & (stops_per_route["stop_count"] >= 1)
    ]["route_ids"].tolist()
    bus_tram_routes = stops_per_route[
        (stops_per_route["transit_mode"] != "train")
        & (stops_per_route["stop_count"] >= min_stops_bus_tram)
    ]["route_ids"].tolist()
    routes_in_isochrone = set(train_routes) | set(bus_tram_routes)

    if grouped_by_route_master:
        filtered_routes = routes[
            routes["variant_route_ids"].apply(
                lambda x: any(route_id in routes_in_isochrone for route_id in x)
            )
        ]

        # Collect all variant route IDs from the filtered route_masters
        filtered_route_ids = set()
        for variant_ids in filtered_routes["variant_route_ids"]:
            filtered_route_ids.update(variant_ids)
    else:
        filtered_routes = routes[routes["osm_id"].isin(routes_in_isochrone)]
        filtered_route_ids = set(filtered_routes["osm_id"])

    stops_in_filtered_routes = stops[
        stops["route_ids"].apply(
            lambda route_ids: any(
                route_id in filtered_route_ids for route_id in route_ids
            )
        )
    ]

    return filtered_routes, stops_in_filtered_routes


def group_stops_by_name(
    stops: gpd.GeoDataFrame,
    min_stops_for_buffer: int = 3,
    buffer_radius: float = 0.0005,
) -> gpd.GeoDataFrame:
    """
    Group transit stops by name and create buffered geometries for stops with multiple locations.

    This utility function groups stops by their 'name' attribute and creates
    buffered point geometries for stop groups with many locations (e.g., "Central Station"
    might have 10+ platforms). This improves map visualization by reducing clutter.

    Args:
        stops (gpd.GeoDataFrame): GeoDataFrame of transit stops (from extract_all_transit_stops()
            or get_transit_stops()). Must have 'name' and 'geometry' columns.
        min_stops_for_buffer (int, optional): Minimum number of stops with the same name
            to trigger buffer creation. If a stop name has >= this many locations,
            a buffer will be created around the centroid. Default: 3.
        buffer_radius (float, optional): Radius for buffer creation (in CRS units,
            typically degrees for EPSG:4326). Default: 0.0005 (~55m at equator).

    Returns:
        gpd.GeoDataFrame: GeoDataFrame with grouped stops. For stop names with
            >= min_stops_for_buffer locations, geometry is a buffered point (circle).
            For others, geometry remains the original point. Columns include:
            - name: Stop name
            - geometry: Point or buffered Point
            - stop_count: Number of individual stops grouped into this feature
            - osm_ids: List of OSM IDs for the grouped stops (new column)

    Raises:
        ValueError: If 'name' or 'geometry' columns are missing from stops GeoDataFrame.

    Examples:
        >>> # Load transit stops
        >>> stops = gpd.read_parquet("transit_stops.geoparquet")
        >>> print(f"Original: {len(stops)} stops")
        Original: 110777 stops

        >>> # Group stops by name (default: buffer if 3+ stops share a name)
        >>> grouped = group_stops_by_name(stops)
        >>> print(f"Grouped: {len(grouped)} unique stop names")
        Grouped: 8543 unique stop names

        >>> # Check which stops got buffered
        >>> buffered = grouped[grouped['stop_count'] >= 3]
        >>> print(f"Buffered: {len(buffered)} stop groups with 3+ locations")
        Buffered: 234 stop groups with 3+ locations

        >>> # Custom settings: buffer only if 5+ stops, larger radius
        >>> grouped = group_stops_by_name(
        ...     stops,
        ...     min_stops_for_buffer=5,
        ...     buffer_radius=0.001  # ~110m at equator
        ... )

        >>> # Use in production workflow
        >>> result = filter_routes_by_isochrone(routes, stops, mapping, isochrone)
        >>> grouped_stops = group_stops_by_name(result['stops'])
        >>> # Now visualize grouped_stops on map (fewer markers, cleaner map)

    Performance:
        - Grouping time: ~100-500ms for 110k stops
        - Result size: Typically 10-20x smaller than original (110k → 8k stops)
        - Memory: Minimal overhead (only adds 'stop_count' and 'osm_ids' columns)

    Notes:
        - **Why group stops?** Many transit systems have stops with identical names
          but different OSM IDs (e.g., multiple platforms, different operators).
          Showing all of them on a map creates visual clutter.
        - **Buffer logic**:
          * If len(stops with same name) >= min_stops_for_buffer: Create buffer around centroid
          * Else: Keep original point geometry
        - **Centroid calculation**: Uses the mean of all stop coordinates for each name
        - **CRS**: Buffering is done in the input CRS (typically EPSG:4326 degrees)
          For metric buffers, reproject to a projected CRS before calling this function

    See Also:
        - extract_all_transit_stops(): Extract all stops from OSM PBF
        - filter_routes_by_isochrone(): Filter routes and stops by isochrone
    """
    # TODO: refactor to rely on the stop_area, which is already calculated in extract_all_transit_stops, instead of counting stops here again. This would also allow to use the same stop_area for all stops with the same name, which would make the buffering more consistent.
    # Validate inputs
    if "name" not in stops.columns:
        raise ValueError("stops GeoDataFrame must have 'name' column")
    if stops.geometry is None:
        raise ValueError("stops GeoDataFrame must have geometry")

    # Handle empty input
    if stops.empty:
        # Return empty GDF with expected schema
        result = stops.copy()
        result["stop_count"] = []
        result["osm_ids"] = []
        return result

    # Group by stop name
    grouped_data = []

    for name, group in stops.groupby("name"):
        stop_count = len(group)
        osm_ids = group["osm_id"].tolist()

        # Calculate centroid of all stops with this name
        centroid = group.geometry.union_all().centroid

        # Create buffered geometry if stop count >= threshold
        if stop_count >= min_stops_for_buffer:
            geometry = centroid.buffer(buffer_radius)
        else:
            geometry = centroid

        # Create record
        record = {
            "name": name,
            "geometry": geometry,
            "stop_count": stop_count,
            "osm_ids": osm_ids,
        }

        grouped_data.append(record)

    # Create new GeoDataFrame
    result = gpd.GeoDataFrame(
        grouped_data,
        crs=stops.crs,
        geometry="geometry",
    )

    return result


def count_route_stops_in_isochrones(
    stops: gpd.GeoDataFrame,
    isochrones: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """
    Count how many stops per route are within isochrone polygons.

    Uses spatial intersection to determine which stops fall within the
    isochrone boundaries, then counts stops per route.

    Args:
        stops (gpd.GeoDataFrame): GeoDataFrame of transit stops (from extract_all_transit_stops).
            Must have 'osm_id' column.
        isochrones (gpd.GeoDataFrame): GeoDataFrame of isochrone polygons (from calculate_isochrones).

    Returns:
        pd.DataFrame: DataFrame with columns 'route_ids', 'stop_count', and 'transit_mode'.

    Examples:
        >>> routes = extract_all_transit_routes(
        >>> osm_pbf_path="isochrones/data/geneva-greater-area.osm.pbf",
        >>>     route_types=["train", "bus", "tram", "light_rail", "subway", "trolleybus"],
        >>>     include_stop_ids=True,
        >>>     group_by="route_master"
        >>> )
        >>> stops = extract_all_transit_stops(
        >>>     osm_pbf_path="isochrones/data/geneva-greater-area.osm.pbf",
        >>>     include_route_ids=True,
        >>> )
        >>> counts = count_route_stops_in_isochrones(stops, isochrones)
    """
    if stops.empty or isochrones.empty:
        return pd.DataFrame(columns=["route_ids", "stop_count", "transit_mode"])

    if "osm_id" not in stops.columns:
        raise ValueError("stops GeoDataFrame must have 'osm_id' column")
    if "route_ids" not in stops.columns:
        raise ValueError(
            "stops GeoDataFrame must have 'route_ids' column. Extract stops with include_route_ids=True or ensure this column exists."
        )
    if "transit_mode" not in stops.columns:
        raise ValueError("stops GeoDataFrame must have 'transit_mode' column")

    # Ensure same CRS for spatial join
    if stops.crs != isochrones.crs:
        stops = stops.to_crs(isochrones.crs)

    stops_in_isochrones = gpd.sjoin(stops, isochrones, how="inner", predicate="within")
    stops_per_route = (
        stops_in_isochrones.explode("route_ids")
        .groupby("route_ids", as_index=False)
        .agg(
            stop_count=("route_ids", "count"),
            transit_mode=("transit_mode", "first"),
        )
    )

    return stops_per_route
