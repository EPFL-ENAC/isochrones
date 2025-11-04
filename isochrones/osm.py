import osmium
import shapely.wkb as wkblib
from shapely.geometry import Point, Polygon

class BBoxFeatureHandler(osmium.SimpleHandler):
    def __init__(self, bbox, tags):
        super().__init__()
        # bbox is expected as (west, south, east, north)
        self.west, self.south, self.east, self.north = bbox
        self.tags = tags or {}
        self.features = []
        self.wkbfab = osmium.geom.WKBFactory()
        self.bbox_poly = Polygon([
            (self.west, self.south),
            (self.west, self.north),
            (self.east, self.north),
            (self.east, self.south)
        ])

    def in_bbox(self, lon, lat):
        return self.south <= lat <= self.north and self.west <= lon <= self.east

    def match_tags(self, obj_tags):
        """
        Match object tags against the requested tags.

        Supported requested tag value types:
        - True: any value for that key is accepted (key must exist)
        - list/tuple/set: accepted values for that key
        - str: exact match
        - None: key existence is enough
        """
        if not self.tags:
            return True

        for key, values in self.tags.items():
            if key not in obj_tags:
                continue
            if values is True:
                return True
            if values is None:
                return True
            if isinstance(values, (list, tuple, set)):
                if obj_tags.get(key) in values:
                    return True
            else:
                # treat as scalar (str/int)
                if str(obj_tags.get(key)) == str(values):
                    return True
        return False

    def node(self, n):
        # nodes have location attribute; skip if missing
        if not hasattr(n, "location") or n.location is None:
            return
        if not self.in_bbox(n.location.lon, n.location.lat):
            return
        if not self.match_tags(n.tags):
            return
        geom = Point(n.location.lon, n.location.lat)
        # include basic identity if available
        self.features.append({
            "geometry": geom,
            "tags": dict(n.tags),
            "osm_type": "node",
            "osm_id": getattr(n, "id", None),
        })

    def way(self, w):
        if not self.match_tags(w.tags):
            return
        try:
            # Try polygon geometry first
            wkb = self.wkbfab.create_multipolygon(w)
        except Exception:
            try:
                wkb = self.wkbfab.create_linestring(w)
            except Exception:
                return
        geom = wkblib.loads(wkb, hex=True)
        if geom.is_valid and geom.intersects(self.bbox_poly):
            self.features.append({
                "geometry": geom,
                "tags": dict(w.tags),
                "osm_type": "way",
                "osm_id": getattr(w, "id", None),
            })

    def relation(self, r):
        if not self.match_tags(r.tags):
            return
        try:
            wkb = self.wkbfab.create_multipolygon(r)
            geom = wkblib.loads(wkb, hex=True)
        except Exception:
            return
        if geom.is_valid and geom.intersects(self.bbox_poly):
            self.features.append({
                "geometry": geom,
                "tags": dict(r.tags),
                "osm_type": "relation",
                "osm_id": getattr(r, "id", None),
            })
