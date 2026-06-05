from __future__ import annotations
import logging
import os
import sys
import numpy as np
from scipy.spatial import KDTree
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from backend.config import (
    WeightCoefficients, PRESET_MODES, TIME_SLOTS, get_time_slot,
    BIDIRECTIONAL_MEET_RADIUS, DEFAULT_AREA, AREA_CONFIGS,
)
from backend.algorithm.cost_function import CostFunction
from backend.algorithm.astar import WeightedAStar
from backend.algorithm.bidirectional_astar import BidirectionalAStar
from backend.algorithm.path_smoother import PathSmoother
from backend.data.osm_loader import OSMLoader
from backend.utils.geoutils import haversine_distance, path_to_coords
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
_osm = OSMLoader()
_loaded_graph = None
_loaded_area = ""
_spatial_tree: Optional[KDTree] = None   
_spatial_ids:  Optional[list]   = None   
def _ensure_graph(area: str = DEFAULT_AREA) -> bool:
    global _loaded_graph, _loaded_area, _spatial_tree, _spatial_ids
    if _loaded_graph is not None and _loaded_area == area:
        return True
    cfg = AREA_CONFIGS.get(area)
    if cfg is None:
        cfg = AREA_CONFIGS[DEFAULT_AREA]
        area = DEFAULT_AREA
    try:
        _loaded_graph = _osm.load_area(
            lat=cfg["lat"], lon=cfg["lon"], dist=cfg["dist"],
        )
        _loaded_area = area
        logger.info("Graph loaded for '%s': %d nodes, %d edges",
                    area, _loaded_graph.number_of_nodes(), _loaded_graph.number_of_edges())
        nodes = list(_loaded_graph.nodes(data=True))
        _spatial_ids = [nid for nid, _ in nodes]
        coords = np.array([[nd.get("y", 0.0), nd.get("x", 0.0)] for _, nd in nodes])
        _spatial_tree = KDTree(coords)
        return True
    except Exception:
        logger.exception("Failed to load graph for area '%s'", area)
        return False
def _build_cost_fn(
    weights: Optional[Dict[str, float]] = None,
    use_dynamic: bool = False,
    hour: Optional[int] = None,
):
    coeffs = WeightCoefficients.from_dict(weights) if weights else WeightCoefficients()
    cf = CostFunction(coeffs)
    _hour = hour
    def cost_fn(current_id: int, neighbor_id: int, tags: Dict, _hour_param: Optional[int] = None) -> float:
        h = _hour if _hour is not None else _hour_param
        if use_dynamic and h is not None:
            return cf.compute_dynamic(tags, h)
        return cf.compute_static(tags)
    return cost_fn
def _find_nearest_node(lat: float, lon: float) -> Optional[int]:
    if _spatial_tree is None:
        return None
    _, idx = _spatial_tree.query([lat, lon])
    return _spatial_ids[idx]
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
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"})
@app.route("/api/time_slots", methods=["GET"])
def list_time_slots():
    return jsonify({
        "time_slots": [
            {
                "name": s.name, "name_cn": s.name_cn,
                "start_hour": s.start_hour, "end_hour": s.end_hour,
                "lighting_multiplier": s.lighting_multiplier,
                "crowd_multiplier": s.crowd_multiplier,
            }
            for s in TIME_SLOTS
        ],
    })
@app.route("/api/preset_modes", methods=["GET"])
def list_preset_modes():
    return jsonify({
        "preset_modes": [
            {
                "id": k,
                "name": v["name"],
                "name_en": v["name_en"],
                "description": v["description"],
                "weights": v["weights"].to_dict(),
            }
            for k, v in PRESET_MODES.items()
        ],
    })
@app.route("/api/apply_preset", methods=["POST"])
def apply_preset():
    data = request.get_json(silent=True) or {}
    mode_id = data.get("mode", "balanced")
    if mode_id not in PRESET_MODES:
        return jsonify({"error": f"Unknown mode: {mode_id}"}), 400
    base = PRESET_MODES[mode_id]["weights"].to_dict()
    overrides = data.get("overrides", {})
    for k, v in overrides.items():
        if k in base:
            base[k] = float(v)
    return jsonify({"mode": mode_id, "mode_name": PRESET_MODES[mode_id]["name"], "weights": base})
@app.route("/api/shortest_path", methods=["POST"])
def shortest_path():
    data = request.get_json(silent=True) or {}
    try:
        start_lat = float(data["start_lat"])
        start_lon = float(data["start_lon"])
        end_lat = float(data["end_lat"])
        end_lon = float(data["end_lon"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Missing or invalid start/end coordinates"}), 400
    hour = int(data.get("hour", 14))
    if not (0 <= hour <= 23):
        hour = 14
    use_bidi = bool(data.get("use_bidirectional", True))
    use_dyn = bool(data.get("use_dynamic_cost", True))
    do_smooth = bool(data.get("smooth_path", True))
    area = str(data.get("area", DEFAULT_AREA))
    mode_id = data.get("mode")
    if mode_id and mode_id in PRESET_MODES:
        weights = PRESET_MODES[mode_id]["weights"].to_dict()
    else:
        weights = PRESET_MODES["balanced"]["weights"].to_dict()
    if isinstance(data.get("weights"), dict):
        for k, v in data["weights"].items():
            weights[k] = float(v)
    if not _ensure_graph(area):
        return jsonify({"error": f"Failed to load map for area '{area}'"}), 503
    start_node = _find_nearest_node(start_lat, start_lon)
    end_node = _find_nearest_node(end_lat, end_lon)
    if start_node is None or end_node is None:
        return jsonify({"error": "Could not map coordinates to road network"}), 400
    cost_fn = _build_cost_fn(weights, use_dyn, hour)
    try:
        if use_bidi:
            searcher = BidirectionalAStar(cost_function=cost_fn, meet_radius=BIDIRECTIONAL_MEET_RADIUS)
            algo = "bidirectional_a*"
        else:
            searcher = WeightedAStar(cost_function=cost_fn)
            algo = "weighted_a*"
        result = searcher.search(_loaded_graph, start_node, end_node, hour)
        if result is None:
            return jsonify({"error": "No path found between the given points"}), 404
        coords = path_to_coords(_loaded_graph, result["path"])
        dist = sum(haversine_distance(coords[i], coords[i + 1]) for i in range(len(coords) - 1))
        if do_smooth and len(coords) > 2:
            smoother = PathSmoother()
            coords = smoother.smooth(coords)
        static_fn = _build_cost_fn(weights, use_dynamic=False)
        static_cost = 0.0
        for u, v in zip(result["path"], result["path"][1:]):
            ed = _loaded_graph.get_edge_data(u, v)
            tags = dict(ed.get("tags", {})) if ed else {}
            static_cost += static_fn(u, v, tags, None)
        slot = get_time_slot(hour)
        resp: Dict[str, Any] = {
            "status": "success",
            "path": coords,
            "path_node_ids": result["path"],
            "total_cost": round(result["cost"], 4),
            "static_cost": round(static_cost, 4),
            "dynamic_cost": round(result["cost"], 4) if use_dyn else None,
            "total_distance_m": round(dist, 1),
            "explored_count": result.get("explored_count", 0),
            "time_slot": slot.name,
            "time_slot_name": slot.name_cn,
            "algorithm": algo,
            "num_nodes": len(result["path"]),
        }
        if "meet_node" in result:
            resp["meet_node"] = result["meet_node"]
            resp["forward_explored"] = result.get("forward_explored", 0)
            resp["backward_explored"] = result.get("backward_explored", 0)
        return jsonify(resp)
    except Exception:
        logger.exception("Path search failed")
        return jsonify({"error": "Internal search error"}), 500
@app.route("/api/compare_modes", methods=["POST"])
def compare_modes():
    data = request.get_json(silent=True) or {}
    try:
        sl = float(data["start_lat"])
        sn = float(data["start_lon"])
        el = float(data["end_lat"])
        en = float(data["end_lon"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Missing or invalid coordinates"}), 400
    area = str(data.get("area", DEFAULT_AREA))
    if not _ensure_graph(area):
        return jsonify({"error": "Failed to load map"}), 503
    snode = _find_nearest_node(sl, sn)
    enode = _find_nearest_node(el, en)
    if snode is None or enode is None:
        return jsonify({"error": "Could not map coordinates"}), 400
    scenarios = data.get("scenarios", [
        {"name": "day_safety", "label": "日间·安全优先", "mode": "blind", "hour": 14, "use_dynamic": True},
        {"name": "night_safety", "label": "夜间·安全优先", "mode": "blind", "hour": 21, "use_dynamic": True},
        {"name": "day_fast", "label": "日间·快速优先", "mode": "balanced", "hour": 14, "use_dynamic": False},
    ])
    results = []
    for sc in scenarios:
        w = PRESET_MODES.get(sc["mode"], PRESET_MODES["balanced"])["weights"].to_dict()
        fn = _build_cost_fn(w, sc.get("use_dynamic", True), sc.get("hour"))
        searcher = BidirectionalAStar(cost_function=fn)
        r = searcher.search(_loaded_graph, snode, enode, sc.get("hour"))
        if r:
            coords = path_to_coords(_loaded_graph, r["path"])
            d = sum(haversine_distance(coords[i], coords[i + 1]) for i in range(len(coords) - 1))
            results.append({
                "name": sc["name"],
                "label": sc["label"],
                "mode": sc["mode"],
                "hour": sc.get("hour", 14),
                "path": coords,
                "cost": round(r["cost"], 4),
                "distance_m": round(d, 1),
                "explored": r.get("explored_count", 0),
                "num_nodes": len(r["path"]),
            })
    return jsonify({
        "status": "success",
        "start": {"lat": sl, "lon": sn},
        "end": {"lat": el, "lon": en},
        "scenarios": results,
        "count": len(results),
    })
@app.route("/api/graph_stats", methods=["GET"])
def graph_stats():
    area = request.args.get("area", DEFAULT_AREA)
    if not _ensure_graph(area):
        return jsonify({"error": "No graph loaded"}), 503
    stats = _osm.get_graph_stats()
    stats["area"] = _loaded_area
    return jsonify(stats)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
