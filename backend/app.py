from __future__ import annotations
import logging
import os
import sys
import threading
import numpy as np
from scipy.spatial import KDTree
from datetime import datetime
from typing import Any, Dict, List, Optional
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from backend.config import (
    WeightCoefficients, PRESET_MODES, get_time_slot,
    BIDIRECTIONAL_MEET_RADIUS, DEFAULT_AREA, AREA_CONFIGS,
)
from backend.algorithm.cost_function import CostFunction
from backend.algorithm.astar import WeightedAStar
from backend.algorithm.bidirectional_astar import BidirectionalAStar
from backend.data.osm_loader import OSMLoader
from backend.utils.geoutils import haversine as haversine_distance, path_to_coords
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
class GraphManager:
    """Manages road network graph loading, caching, and spatial indexing.

    Encapsulates global mutable state with thread-safe graph loading and nearest-neighbor queries.
    """

    def __init__(self) -> None:
        self._osm = OSMLoader()
        self._graph = None
        self._area = ""
        self._spatial_tree: Optional[KDTree] = None
        self._spatial_ids: Optional[list] = None
        self._loading = False
        self._lock = threading.Lock()

    # ── Public Properties ──

    @property
    def graph(self):
        return self._graph

    @property
    def loaded_area(self) -> str:
        return self._area

    @property
    def is_loading(self) -> bool:
        return self._loading

    @property
    def is_ready(self) -> bool:
        return self._graph is not None

    # ── Graph Loading ──

    def ensure_graph(self, area_or_cfg: str | Dict[str, Any] = DEFAULT_AREA) -> bool:
        """Ensure the road network graph is loaded (thread-safe).

        Args:
          area_or_cfg: Predefined area name (str), or a config dict with lat/lon/dist.
                       When a dict is passed, a dynamic area ID is generated.
        """
        area_key = area_or_cfg if isinstance(area_or_cfg, str) else "custom"

        if self._graph is not None and self._area == area_key:
            return True
        if self._loading:
            return False
        with self._lock:
            if self._graph is not None and self._area == area_key:
                return True

            if isinstance(area_or_cfg, str):
                cfg = AREA_CONFIGS.get(area_or_cfg)
                if cfg is None:
                    cfg = AREA_CONFIGS[DEFAULT_AREA]
                    area_key = DEFAULT_AREA
                lat, lon, dist = cfg["lat"], cfg["lon"], cfg["dist"]
            else:
                lat = area_or_cfg["lat"]
                lon = area_or_cfg["lon"]
                dist = area_or_cfg["dist"]
                # Generate unique key for cache differentiation
                area_key = f"auto_{lat:.2f}_{lon:.2f}_{int(dist)}"

            self._loading = True
            try:
                self._graph = self._osm.load_area(
                    lat=lat, lon=lon, dist=dist,
                    area=area_key,
                )
                self._area = area_key
                logger.info("Graph loaded for '%s': %d nodes, %d edges",
                            area_key, self._graph.number_of_nodes(), self._graph.number_of_edges())
                self._rebuild_spatial_index()
                return True
            except Exception:
                logger.exception("Failed to load graph for area '%s'", area_key)
                return False
            finally:
                self._loading = False

    def preload_default(self) -> None:
        """Preload the default area graph in a background thread."""
        logger.info("Pre-loading graph for default area '%s'...", DEFAULT_AREA)
        self.ensure_graph(DEFAULT_AREA)

    # ── Spatial Index ──

    def _rebuild_spatial_index(self) -> None:
        """Rebuild KDTree spatial index from the current graph."""
        nodes = list(self._graph.nodes(data=True))
        self._spatial_ids = [nid for nid, _ in nodes]
        coords = np.array([[nd.get("y", 0.0), nd.get("x", 0.0)] for _, nd in nodes])
        self._spatial_tree = KDTree(coords)

    def find_nearest_node(self, lat: float, lon: float) -> Optional[int]:
        """Find the nearest graph node to (lat, lon), always returns the closest."""
        if self._spatial_tree is None or not self._spatial_ids:
            return None
        _dist, idx = self._spatial_tree.query([lat, lon])
        return self._spatial_ids[idx]


# ── Global Graph Manager Instance ──
graph_mgr = GraphManager()
threading.Thread(target=graph_mgr.preload_default, daemon=True).start()
def _build_cost_fn(
    weights: Optional[Dict[str, float]] = None,
    use_dynamic: bool = False,
    hour: Optional[int] = None,
):
    coeffs = WeightCoefficients.from_dict(weights) if weights else WeightCoefficients()
    cf = CostFunction(coeffs)

    if use_dynamic:
        def cost_fn(current_id: int, neighbor_id: int, tags: Dict, _hour: Optional[int] = None) -> float:
            h = hour if hour is not None else _hour
            if h is not None:
                return cf.compute_dynamic(tags, h)
            return cf.compute_static(tags)
    else:
        def cost_fn(current_id: int, neighbor_id: int, tags: Dict, _hour: Optional[int] = None) -> float:
            return cf.compute_static(tags)
    return cost_fn
FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "frontend", "public",
)
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")
@app.route("/<path:filename>")
def static_files(filename: str):
    return send_from_directory(FRONTEND_DIR, filename)
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "graph_ready": graph_mgr.is_ready,
        "graph_loading": graph_mgr.is_loading,
        "loaded_area": graph_mgr.loaded_area or None,
    })
@app.route("/api/shortest_path", methods=["POST"])
def shortest_path():
    data = request.get_json(silent=True) or {}
    try:
        start_lat = float(data["start_lat"])
        start_lon = float(data["start_lon"])
        end_lat = float(data["end_lat"])
        end_lon = float(data["end_lon"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Missing start or end coordinates"}), 400
    hour = int(data.get("hour", 14))
    if not (0 <= hour <= 23):
        hour = 14
    use_bidi = bool(data.get("use_bidirectional", True))
    use_dyn = bool(data.get("use_dynamic_cost", True))
    area = str(data.get("area", DEFAULT_AREA))

    if abs(start_lat) < 0.1 and abs(start_lon) < 0.1:
        return jsonify({
            "status": "error",
            "error": "Invalid coordinates (0,0), please enter valid lat/lng"
        }), 400

    if start_lat == end_lat and start_lon == end_lon:
        slot = get_time_slot(hour)
        return jsonify({
            "status": "success",
            "path": [[start_lat, start_lon]],
            "path_node_ids": [],
            "total_cost": 0.0,
            "static_cost": 0.0,
            "dynamic_cost": 0.0 if use_dyn else None,
            "total_distance_m": 0,
            "time_slot": slot.name,
            "time_slot_name": slot.name,
            "algorithm": "direct_arrival_bypass",
            "num_nodes": 1,
        })

    mode_id = data.get("mode")
    if mode_id and mode_id in PRESET_MODES:
        weights = PRESET_MODES[mode_id]["weights"].to_dict()
    else:
        weights = PRESET_MODES["balanced"]["weights"].to_dict()
    if isinstance(data.get("weights"), dict):
        for k, v in data["weights"].items():
            weights[k] = float(v)

    # ── Dynamically determine load area ──
    # Center on midpoint of start/end, radius = distance + buffer
    _MIN_DIST = 1500  # Minimum load radius 1.5km
    _BUFFER = 1.3     # Buffer coefficient 30%
    mid_lat = (start_lat + end_lat) / 2
    mid_lon = (start_lon + end_lon) / 2
    span = haversine_distance((start_lat, start_lon), (end_lat, end_lon))
    load_dist = max(int(span * _BUFFER), _MIN_DIST)

    # Check if predefined area covers current coords, otherwise load dynamically
    # e.g. if user picks "Kuala Lumpur" but sets coords in NYC, it auto-loads NYC map
    if area in AREA_CONFIGS:
        cfg = AREA_CONFIGS[area]
        dist_from_center = haversine_distance((mid_lat, mid_lon), (cfg["lat"], cfg["lon"]))
        if dist_from_center <= cfg["dist"] * 1.2:  # Within area (with 20% buffer)
            load_arg: Any = area
        else:
            load_arg = {"lat": mid_lat, "lon": mid_lon, "dist": load_dist}
    else:
        load_arg = {"lat": mid_lat, "lon": mid_lon, "dist": load_dist}

    if not graph_mgr.ensure_graph(load_arg):
        return jsonify({"error": "Map data still loading, please try again (first launch downloads from OpenStreetMap)"}), 503
    start_node = graph_mgr.find_nearest_node(start_lat, start_lon)
    end_node = graph_mgr.find_nearest_node(end_lat, end_lon)
    if start_node is None:
        return jsonify({"error": "No road network data near start point"}), 400
    if end_node is None:
        return jsonify({"error": "No road network data near end point"}), 400
    cost_fn = _build_cost_fn(weights, use_dyn, hour)
    try:
        if use_bidi:
            searcher = BidirectionalAStar(cost_function=cost_fn, meet_radius=BIDIRECTIONAL_MEET_RADIUS)
            algo = "bidirectional_a*"
        else:
            searcher = WeightedAStar(cost_function=cost_fn)
            algo = "weighted_a*"
        result = searcher.search(graph_mgr.graph, start_node, end_node, hour)
        if result is None:
            return jsonify({"error": "No feasible path found between start and end"}), 404
        coords = path_to_coords(graph_mgr.graph, result["path"])
        dist = sum(haversine_distance(coords[i], coords[i + 1]) for i in range(len(coords) - 1))
        # Use _edge_tags (with length) to ensure correct static_cost
        from backend.algorithm.astar import _edge_tags as _fetch_edge_tags
        static_fn = _build_cost_fn(weights, use_dynamic=False)
        static_cost = 0.0
        for u, v in zip(result["path"], result["path"][1:]):
            tags = _fetch_edge_tags(graph_mgr.graph, u, v)
            static_cost += static_fn(u, v, tags, None)
        slot = get_time_slot(hour)

        # ── Route Feature Analysis (based on OSM tag defaults) ──
        tactile_count = 0
        steps_count = 0
        lit_count = 0
        sidewalk_count = 0
        highway_stats: Dict[str, int] = {}
        total_edges = 0
        for u, v in zip(result["path"], result["path"][1:]):
            ed = graph_mgr.graph.get_edge_data(u, v)
            tags = dict(ed.get("tags", {})) if ed else {}
            total_edges += 1
            if str(tags.get("tactile_paving", "no")).lower() == "yes":
                tactile_count += 1
            if str(tags.get("steps", "no")).lower() == "yes":
                steps_count += 1
            if str(tags.get("lit", "no")).lower() in ("yes", "24/7", "automatic"):
                lit_count += 1
            if str(tags.get("sidewalk", "no")).lower() in ("yes", "both", "left", "right", "separate"):
                sidewalk_count += 1
            hw = str(tags.get("highway", "unknown")).lower()
            highway_stats[hw] = highway_stats.get(hw, 0) + 1

        top_highways = sorted(highway_stats.items(), key=lambda x: -x[1])[:3]

        def _pct(n: int) -> float:
            return round(n / total_edges * 100, 0) if total_edges else 0

        analysis: Dict[str, Any] = {
            "total_edges": total_edges,
            "tactile_paving_pct": _pct(tactile_count),
            "steps_count": steps_count,
            "lit_pct": _pct(lit_count),
            "sidewalk_pct": _pct(sidewalk_count),
            "top_highways": [{"name": k, "pct": _pct(v)} for k, v in top_highways],
        }

        resp: Dict[str, Any] = {
            "status": "success",
            "path": coords,
            "path_node_ids": result["path"],
            "total_cost": round(result["cost"], 4),
            "static_cost": round(static_cost, 4),
            "dynamic_cost": round(result["cost"] - static_cost, 4) if use_dyn else None,
            "total_distance_m": round(dist, 1),
            "explored_count": result.get("explored_count", 0),
            "time_slot": slot.name,
            "time_slot_name": slot.name,
            "algorithm": algo,
            "num_nodes": len(result["path"]),
            "route_analysis": analysis,
        }
        if "meet_node" in result:
            resp["meet_node"] = result["meet_node"]
            resp["forward_explored"] = result.get("forward_explored", 0)
            resp["backward_explored"] = result.get("backward_explored", 0)
        return jsonify(resp)
    except Exception:
        logger.exception("Path search failed")
        return jsonify({"error": "Internal path search error, please retry"}), 500
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
