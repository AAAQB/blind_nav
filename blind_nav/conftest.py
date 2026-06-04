from __future__ import annotations
import sys
import os
from typing import Generator
import pytest
import networkx as nx
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
@pytest.fixture
def unit_grid_3x3() -> nx.Graph:
    G = nx.Graph()
    for r in range(3):
        for c in range(3):
            G.add_node(r * 3 + c, y=float(r), x=float(c))
    edges = [
        (0, 1), (1, 2), (3, 4), (4, 5), (6, 7), (7, 8),
        (0, 3), (3, 6), (1, 4), (4, 7), (2, 5), (5, 8),
    ]
    for u, v in edges:
        G.add_edge(u, v, tags={})
    return G
@pytest.fixture
def unit_grid_10x10() -> nx.Graph:
    size = 10
    G = nx.Graph()
    for r in range(size):
        for c in range(size):
            G.add_node(r * size + c, y=r / 10.0, x=c / 10.0)
    for r in range(size):
        for c in range(size):
            n = r * size + c
            if c + 1 < size:
                G.add_edge(n, r * size + c + 1, tags={})
            if r + 1 < size:
                G.add_edge(n, (r + 1) * size + c, tags={})
    return G