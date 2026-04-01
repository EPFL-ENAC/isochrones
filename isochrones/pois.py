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
    else:
        filtered_routes = routes[routes["osm_id"].isin(routes_in_isochrone)]

    # Repeat the process for the stops, only counting those that appear in the filtered routes
    filtered_route_ids = set(filtered_routes["osm_id"])
    stops_in_filtered_routes = stops[
        stops["route_ids"].apply(
            lambda route_ids: any(
                route_id in filtered_route_ids for route_id in route_ids
            )
        )
    ]

    return filtered_routes, stops_in_filtered_routes


def group_stops_by_stop_area(
    stops: gpd.GeoDataFrame,
    min_stops_for_buffer: int = 3,
    buffer_radius: float = 0.0005,
) -> gpd.GeoDataFrame:
    """
    Group transit stops by stop_area and create buffered geometries for stop groups with multiple locations.

    This function groups stops by their OSM stop_area relation ID, which represents the logical
    grouping of all physical elements of a transit stop (platforms, stop positions, entrances, etc.).
    Stops without a stop_area_id remain as individual entries in the output.

    Args:
        stops (gpd.GeoDataFrame): GeoDataFrame of transit stops (from extract_all_transit_stops()).
            Must have 'stop_area_id', 'stop_area_name', 'osm_id', 'name', and 'geometry' columns.
        min_stops_for_buffer (int, optional): Minimum number of stops in a stop_area
            to trigger buffer creation. If a stop_area has >= this many stops,
            a buffer will be created around the centroid. Default: 3.
        buffer_radius (float, optional): Radius for buffer creation (in CRS units,
            typically degrees for EPSG:4326). Default: 0.0005 (~55m at equator).

    Returns:
        gpd.GeoDataFrame: GeoDataFrame with grouped stops. Columns include:
            - stop_area_id: Stop area OSM ID (or individual stop osm_id if not in a stop_area)
            - stop_area_name: Stop area name (or individual stop name if not in a stop_area)
            - geometry: Point or buffered Point (buffered if stop_count >= min_stops_for_buffer)
            - stop_count: Number of individual stops in this stop_area (1 if ungrouped)
            - osm_ids: List of OSM IDs for the stops in this group

    Raises:
        ValueError: If required columns are missing from stops GeoDataFrame.

    Examples:
        >>> # Load transit stops (includes stop_area information)
        >>> stops = gpd.read_parquet("transit_stops.geoparquet")
        >>> print(f"Original: {len(stops)} stops")
        Original: 110777 stops

        >>> # Group stops by stop_area (default: buffer if 3+ stops share a stop_area)
        >>> grouped = group_stops_by_stop_area(stops)
        >>> print(f"Grouped: {len(grouped)} unique stop areas")
        Grouped: 95432 stop areas (includes ungrouped stops)

        >>> # Check which stop areas got buffered
        >>> buffered = grouped[grouped['stop_count'] >= 3]
        >>> print(f"Buffered: {len(buffered)} stop areas with 3+ stops")
        Buffered: 156 stop areas with 3+ stops

        >>> # Custom settings: buffer only if 5+ stops, larger radius
        >>> grouped = group_stops_by_stop_area(
        ...     stops,
        ...     min_stops_for_buffer=5,
        ...     buffer_radius=0.001  # ~110m at equator
        ... )

        >>> # Use in production workflow
        >>> routes, stops = filter_routes_by_isochrone(routes, stops, isochrone)
        >>> grouped_stops = group_stops_by_stop_area(stops)

    See Also:
        - extract_all_transit_stops(): Extract stops with stop_area information from OSM PBF
        - filter_routes_by_isochrone(): Filter routes and stops by isochrone
    """
    # Validate inputs
    required_columns = ["stop_area_id", "stop_area_name", "osm_id", "name"]
    missing_columns = [col for col in required_columns if col not in stops.columns]
    if missing_columns:
        raise ValueError(
            f"stops GeoDataFrame must have columns: {missing_columns}. "
            "Extract stops with extract_all_transit_stops() to get stop_area information."
        )
    if stops.geometry is None:
        raise ValueError("stops GeoDataFrame must have geometry")

    # Handle empty input
    if stops.empty:
        # Return empty GDF with expected schema
        result = gpd.GeoDataFrame(
            {
                "stop_area_id": [],
                "stop_area_name": [],
                "geometry": [],
                "stop_count": [],
                "osm_ids": [],
            },
            crs=stops.crs,
            geometry="geometry",
        )
        return result

    # Separate stops with and without stop_area
    stops_with_area = stops[stops["stop_area_id"].notna()].copy()
    stops_without_area = stops[stops["stop_area_id"].isna()].copy()

    grouped_data = []

    # Group stops by stop_area_id
    if not stops_with_area.empty:
        for stop_area_id, group in stops_with_area.groupby("stop_area_id"):
            stop_count = len(group)
            osm_ids = group["osm_id"].tolist()

            # Use stop_area_name (consistent across all stops in the group)
            stop_area_name = group["stop_area_name"].iloc[0]

            # Calculate centroid of all stops in this stop_area
            centroid = group.geometry.union_all().centroid

            # Create buffered geometry if stop count >= threshold
            if stop_count >= min_stops_for_buffer:
                geometry = centroid.buffer(buffer_radius)
            else:
                geometry = centroid

            grouped_data.append(
                {
                    "stop_area_id": stop_area_id,
                    "stop_area_name": stop_area_name,
                    "geometry": geometry,
                    "stop_count": stop_count,
                    "osm_ids": osm_ids,
                }
            )

    # Add ungrouped stops (no stop_area) as individual entries
    if not stops_without_area.empty:
        for _, stop in stops_without_area.iterrows():
            grouped_data.append(
                {
                    "stop_area_id": stop["osm_id"],  # Use stop osm_id as identifier
                    "stop_area_name": stop["name"],  # Use original stop name
                    "geometry": stop.geometry,  # Keep original point (no buffer)
                    "stop_count": 1,
                    "osm_ids": [stop["osm_id"]],
                }
            )

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
