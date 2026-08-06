from __future__ import annotations
import logging
import os
import pickle
from typing import Any, Dict, Optional
import networkx as nx
from backend.config import (
    HIGHWAY_TAG_DEFAULTS, FALLBACK_DEFAULTS, REGION_TAG_OVERRIDES, OSM_NETWORK_TYPE,
)
logger = logging.getLogger(__name__)
_ACCESSIBILITY_KEYS = frozenset({
    "tactile_paving", "steps", "surface", "lit", "sidewalk",
    "highway", "incline", "width",
})
class OSMLoader:
    def __init__(self, cache_dir: Optional[str] = None) -> None:
        base = cache_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "osm_cache",
        )
        self._cache_dir = base
        os.makedirs(self._cache_dir, exist_ok=True)
        self._graph: Optional[nx.Graph] = None
    def load_area(
        self,
        lat: float,
        lon: float,
        dist: float = 1000.0,
        network_type: str = OSM_NETWORK_TYPE,
        force_reload: bool = False,
        area: str = "",
    ) -> nx.Graph:
        import osmnx as ox
        key = f"walk_{lat:.4f}_{lon:.4f}_{int(dist)}"
        cache_path = os.path.join(self._cache_dir, f"{key}.pkl")
        if not force_reload:
            cached = self._load_cache(cache_path)
            if cached is not None:
                return cached
        G_multi = ox.graph_from_point(
            (lat, lon),
            dist=dist,
            network_type=network_type,
            simplify=False,
            retain_all=True,
        )
        self._enrich_tags(G_multi, area=area)
        G = _to_undirected(G_multi)
        self._save_cache(G, cache_path)
        self._graph = G
        logger.info("Loaded %s: %d nodes, %d edges", key, G.number_of_nodes(), G.number_of_edges())
        return G
    def load_bbox(
        self,
        north: float, south: float, east: float, west: float,
        network_type: str = OSM_NETWORK_TYPE,
        force_reload: bool = False,
        area: str = "",
    ) -> nx.Graph:
        import osmnx as ox
        key = f"{network_type}_{north:.4f}_{south:.4f}_{east:.4f}_{west:.4f}"
        cache_path = os.path.join(self._cache_dir, f"{key}.pkl")
        if not force_reload:
            cached = self._load_cache(cache_path)
            if cached is not None:
                return cached
        G_multi = ox.graph_from_bbox(
            north=north, south=south, east=east, west=west,
            network_type=network_type, simplify=True, retain_all=True,
        )
        self._enrich_tags(G_multi, area=area)
        G = _to_undirected(G_multi)
        self._save_cache(G, cache_path)
        self._graph = G
        return G
    def load_from_file(self, path: str) -> nx.Graph:
        with open(path, "rb") as f:
            G = pickle.load(f)
        self._graph = G
        return G
    def save_to_file(self, path: str) -> None:
        if self._graph is not None:
            with open(path, "wb") as f:
                pickle.dump(self._graph, f)
    @property
    def graph(self) -> Optional[nx.Graph]:
        return self._graph
    def get_graph_stats(self) -> Dict[str, Any]:
        if self._graph is None:
            return {"nodes": 0, "edges": 0}
        n = self._graph.number_of_nodes()
        e = self._graph.number_of_edges()
        return {"nodes": n, "edges": e, "avg_degree": (2 * e) / max(n, 1)}
    def _enrich_tags(self, G_multi: nx.MultiDiGraph, area: str = "") -> None:
        """Fill in missing OSM tags for all edges.

        Priority (low to high):
          1. FALLBACK_DEFAULTS (global fallback)
          2. HIGHWAY_TAG_DEFAULTS (per-highway-type defaults)
          3. REGION_TAG_OVERRIDES[area] (regional overrides, if area is non-empty)
          4. Original OSM data (highest priority, preserved via setdefault)
        """
        region_overrides = REGION_TAG_OVERRIDES.get(area, {})

        for _u, _v, _k, data in G_multi.edges(keys=True, data=True):
            tags = data.setdefault("tags", {})
            hw = data.get("highway", "unclassified")
            if isinstance(hw, (list, tuple)):
                hw = hw[0] or "unclassified"
            hw = str(hw).lower()
            tags.setdefault("highway", hw)

            # Layer 1: per-highway-type defaults
            defaults = HIGHWAY_TAG_DEFAULTS.get(hw, FALLBACK_DEFAULTS)
            # Layer 2: regional overrides (merged into defaults, higher priority)
            hw_overrides = region_overrides.get(hw, {})
            merged = {**defaults, **hw_overrides}

            for k, default_val in merged.items():
                if k not in tags or tags[k] is None:
                    tags[k] = default_val

            for k, v in tags.items():
                data[k] = v
    def _load_cache(self, path: str) -> Optional[nx.Graph]:
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return pickle.load(f)
            except Exception as exc:
                logger.warning("Cache read failed for %s: %s", path, exc)
        return None
    def _save_cache(self, G: nx.Graph, path: str) -> None:
        try:
            with open(path, "wb") as f:
                pickle.dump(G, f)
        except Exception as exc:
            logger.warning("Cache write failed for %s: %s", path, exc)
def _to_undirected(G_multi: nx.MultiDiGraph) -> nx.Graph:
    H = nx.Graph()
    for n, nd in G_multi.nodes(data=True):
        H.add_node(n, **nd)
    for u, v, k, ed in G_multi.edges(keys=True, data=True):
        if not H.has_edge(u, v):
            H.add_edge(u, v, **ed)
    return H