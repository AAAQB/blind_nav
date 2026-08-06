# BlindNav — Smart Navigation for the Visually Impaired

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0%2B-lightgrey)](https://flask.palletsprojects.com)
[![React](https://img.shields.io/badge/Frontend-React+MapLibre-61dafb)](https://reactjs.org)
[![OSMnx](https://img.shields.io/badge/OSM-Osmnx%201.9%2B-green)](https://osmnx.readthedocs.io)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

**BlindNav** is an accessibility-aware route planning system designed specifically for **visually impaired pedestrians**. It computes optimal walking routes by factoring in real-world street conditions — tactile paving, steps, surface quality, sidewalk availability, lighting, road width, and incline — using OpenStreetMap data and weighted cost functions.

> **Demo:** Navigate cities like Singapore, Tokyo, and Berlin with a rich, interactive map interface.

---

## Table of Contents

- [Features](#features)
- [System Architecture](#system-architecture)
- [Screenshots](#screenshots)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Running the Application](#running-the-application)
- [Usage Guide](#usage-guide)
  - [Navigation Modes](#navigation-modes)
  - [Time-Aware Routing](#time-aware-routing)
  - [Route Analysis](#route-analysis)
- [Algorithm Details](#algorithm-details)
  - [Accessibility Cost Function](#accessibility-cost-function)
  - [Time-Dependent Dynamic Cost](#time-dependent-dynamic-cost)
  - [Weighted Bidirectional A\* (Fusion Algorithm)](#weighted-bidirectional-a-fusion-algorithm)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Configuration](#configuration)
  - [Navigation Modes](#navigation-modes-1)
  - [Area Definitions](#area-definitions)
  - [Region Tag Overrides](#region-tag-overrides)
- [Data Sources](#data-sources)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Accessibility-First Routing** — Routes are scored on tactile paving, steps, surface smoothness, sidewalk presence, lighting, road width, and incline.
- **Multi-City Support** — Pre-configured for Kuala Lumpur, Singapore, Tokyo, and Berlin, with dynamic area loading for any location worldwide.
- **Time-Aware Dynamic Costs** — Lighting and crowd multipliers adjust route costs by hour of day (dawn, day, dusk, night, late night).
- **Multiple Navigation Modes** — Preset weight profiles for Blind, Wheelchair, Elderly, and Balanced preferences.
- **Interactive Map UI** — Built with React + MapLibre GL JS. Click to set start/end points, switch map styles, and view route details.
- **Rich Route Analysis** — Per-route statistics including tactile paving coverage, lighting percentage, sidewalk availability, steps count, and road type breakdown.
- **Weighted Bidirectional A\* Algorithm** — A fusion of weighted heuristic search and bidirectional meet-in-the-middle expansion for optimal accessibility-aware pathfinding.
- **RESTful API** — Clean Flask backend with JSON endpoints for seamless integration.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Browser)                     │
│  ┌─────────────────────────────────────────────────────┐ │
│  │   React SPA · MapLibre GL JS · MapTiles / OSM       │ │
│  └───────────────────────┬─────────────────────────────┘ │
│                          │ HTTP / JSON                    │
├──────────────────────────┼──────────────────────────────┤
│                    Backend (Flask)                        │
│  ┌───────────────────────┴─────────────────────────────┐ │
│  │  /api/shortest_path   /api/health                    │ │
│  │  GraphManager · KDTree spatial index                 │ │
│  └───────────────────────┬─────────────────────────────┘ │
│                          │                               │
│  ┌───────────────────────┴─────────────────────────────┐ │
│  │  Algorithm Layer                                     │ │
│  │  ┌──────────────────────────────────────────────┐   │ │
│  │  │  Weighted A* · Bidirectional A*              │   │ │
│  │  │  CostFunction · StaticCost · TimeDependentCost│   │ │
│  │  └──────────────────────────────────────────────┘   │ │
│  └───────────────────────┬─────────────────────────────┘ │
│                          │                               │
│  ┌───────────────────────┴─────────────────────────────┐ │
│  │  Data Layer                                          │ │
│  │  ┌──────────────────────────────────────────────┐   │ │
│  │  │  OSMLoader · OSMnx · Pickle Cache            │   │ │
│  │  └──────────────────────────────────────────────┘   │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

The application follows a three-tier architecture:

1. **Frontend** — Single-page application built with vanilla React (no build step) and MapLibre GL JS for map rendering.
2. **Backend** — Flask server providing REST API endpoints for path computation and health status.
3. **Data** — OpenStreetMap data fetched via OSMnx, enriched with accessibility tags, and cached locally as pickle files.

---

## Getting Started

### Prerequisites

- **Python** 3.10 or higher
- **pip** (Python package manager)
- A modern web browser (Chrome, Firefox, Edge, Safari)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/blindnav.git
   cd blindnav
   ```

2. **Create and activate a virtual environment (recommended)**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

   > **Note:** OSMnx has system-level dependencies on Windows. If you encounter issues, consider using [WSL](https://learn.microsoft.com/en-us/windows/wsl/) or consult the [OSMnx installation guide](https://osmnx.readthedocs.io/en/stable/installation.html).

4. **Pre-download OSM data (optional but recommended)**
   ```bash
   python scripts/download_osm_data.py --area all
   ```
   This downloads the road network for all pre-configured cities. The data is cached in `data/osm_cache/` for faster subsequent loads.

### Running the Application

1. **Start the Flask server**
   ```bash
   python backend/app.py
   ```
   The server starts on `http://0.0.0.0:5000` by default.

2. **Open the application**
   Navigate to [http://localhost:5000](http://localhost:5000) in your browser.

3. **Optional: Change port or enable debug mode**
   ```bash
   PORT=8080 DEBUG=1 python backend/app.py
   ```

---

## Usage Guide

### Navigation Modes

BlindNav offers four preset navigation modes, each with specially tuned weight coefficients:

| Mode | Description | Key Priorities |
|------|-------------|----------------|
| **Blind** | For visually impaired users | Tactile paving (×5.0), sidewalks (×4.0), avoids steps |
| **Wheelchair** | For wheelchair users | Step-free (×5.0), wide paths (×4.0), smooth surfaces (×3.5) |
| **Elderly** | For elderly pedestrians | Good lighting (×3.0), smooth surfaces (×3.0), gentle slopes (×2.5) |
| **Balanced** | Generic pedestrian | Moderate preferences across all factors |

### Time-Aware Routing

The time slider (0:00 – 23:00) controls how lighting and crowd conditions affect route costs:

| Time Slot | Hours | Lighting Multiplier | Crowd Multiplier | Behavior |
|-----------|-------|---------------------|------------------|----------|
| **Late Night** | 23:00–05:00 | ×2.0 | ×0.8 | Unlit paths penalized; quiet roads preferred |
| **Dawn** | 05:00–07:00 | ×1.5 | ×0.8 | Early morning, sparse crowd |
| **Day** | 07:00–18:00 | ×0.5 | ×1.0 | Best for unlit paths; normal crowd |
| **Dusk** | 18:00–20:00 | ×1.5 | ×1.2 | Moderate lighting penalty; busy |
| **Night** | 20:00–23:00 | ×3.0 | ×1.5 | Heavy penalty on unlit paths; busy |

At night, the dynamic cost model triples the cost of unlit segments, naturally steering routes toward well-lit streets and main roads.

### Route Analysis

After computing a route, the sidebar displays detailed analytics:

- **Distance** — Total path length in meters
- **Estimated Time** — Walking time at ~1.4 m/s
- **Total Cost** — Aggregated accessibility cost score
- **Nodes Explored** — How many graph nodes were visited during search
- **Route Analysis Bars**:
  - **Tactile Paving** — Percentage of edges with tactile paving
  - **Lighting** — Percentage of edges that are lit
  - **Sidewalk** — Percentage of edges with sidewalks
- **Smart Notes** — Natural language suggestions (e.g., "Good tactile paving coverage", "No steps on route")

---

## Algorithm Details

### Accessibility Cost Function

The core innovation of BlindNav is its **multi-factor accessibility cost function**. Each road segment (edge) in the graph is scored according to:

$$C_{\text{static}}(e) = \left( \sum_{i} w_i \cdot s_i \right) \cdot \max(\text{length}(e), L_{\text{ref}})$$

Where:
- $w_i$ = user-configurable weight for factor $i$
- $s_i$ = score for factor $i$ (from OSM tags)
- $L_{\text{ref}}$ = reference length (1.0 m), prevents distortion on extremely short edges

**Factors evaluated:**

| Factor | Weight (Default) | Score Range | Description |
|--------|------------------|-------------|-------------|
| Tactile Paving | 3.0 | 1.0 – 10.0 | Guiding ground indicators for the blind |
| Steps | 5.0 | 0.0 – 15.0 | Staircases (heavily penalized) |
| Surface | 2.0 | 1.0 – 9.0 | Asphalt=1.0, gravel=7.0, sand=9.0 |
| Lighting | 2.0 | 0.0 – 5.0 | Street lighting availability |
| Sidewalk | 2.5 | 0.0 – 8.0 | Presence of pedestrian walkways |
| Highway Type | 1.5 | 1.0 – 10.0 | Road classification (footway=1, motorway=10) |
| Incline | 1.5 | 0.0 – 8.0 | Slope steepness |
| Width | 1.0 | 0.0 – 6.0 | Path width (penalty if < 2.0 m) |

### Time-Dependent Dynamic Cost

The dynamic cost model adjusts the static cost by time-of-day multipliers:

$$C_{\text{dynamic}}(e, t) = C_{\text{static}}(e) \cdot M_{\text{lit}}(t, e) \cdot M_{\text{crowd}}(t, e)$$

Where:
- $M_{\text{lit}}$ = lighting multiplier from the time slot (applied only to unlit/unknown segments)
- $M_{\text{crowd}} = \max(0.6,\ 1.0 + (m_{\text{slot}} - 1.0) \cdot w_{\text{traffic}})$
  - $m_{\text{slot}}$ = crowd multiplier for the current time slot
  - $w_{\text{traffic}}$ = traffic weight for the road type (motorway=2.0, footway=0.6, etc.)

### Weighted Bidirectional A\* (Fusion Algorithm)

BlindNav's core pathfinder fuses **weighted heuristic search** with **bidirectional meet-in-the-middle expansion**, combining the strengths of both approaches:

- **Weighted Heuristic:** Each expansion step uses the priority function $f(n) = g(n) + w \cdot h(n)$ where $w = 1.0$ (admissible) by default and $h(n)$ is the approximate Euclidean distance (accounting for latitude scaling), well-aligned with the metric cost dimension.
- **Bidirectional Expansion:** Two frontiers grow simultaneously — one forward from the start node and one backward from the goal node — alternating expansion to balance progress.
- **Meeting Detection:** When a node appears in both closed sets, a candidate solution is found.
- **Early Termination:** If the minimum $f$-scores of both frontiers exceed the best known total cost, no better path can exist and the search stops immediately.
- **Path Reconstruction:** Forward half from start to meet node, backward half from meet node to goal.
- **Dead-end Detection:** The search exhausts its frontier up to 200,000 iterations.

This fusion typically explores **far fewer nodes** than standard unidirectional A\*, especially in large road networks, while retaining the optimality guarantees of a weighted heuristic.

---

## Project Structure

```
├── backend/
│   ├── __init__.py
│   ├── app.py                  # Flask application entry point & API routes
│   ├── config.py               # Score maps, weights, area configs, time slots
│   ├── algorithm/
│   │   ├── __init__.py
│   │   ├── astar.py            # Weighted A* search implementation
│   │   ├── bidirectional_astar.py  # Bidirectional A* with meet-in-the-middle
│   │   └── cost_function.py    # Static & time-dependent cost computation
│   ├── data/
│   │   ├── __init__.py
│   │   └── osm_loader.py       # OSM graph loading, tag enrichment, caching
│   ├── models/
│   │   └── __init__.py
│   └── utils/
│       ├── __init__.py
│       └── geoutils.py         # Haversine, Euclidean approx, bearing
├── frontend/
│   └── public/
│       └── index.html          # Single-page React application
├── scripts/
│   └── download_osm_data.py    # Pre-download OSM data for configured areas
├── data/
│   └── osm_cache/              # Pickle cache of downloaded OSM graphs
├── cache/                      # API-level JSON cache
├── logs/                       # Application logs
└── requirements.txt            # Python dependencies
```

---

## API Reference

### `GET /api/health`

Returns the server and graph loading status.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2026-06-20T12:00:00Z",
  "graph_ready": true,
  "graph_loading": false,
  "loaded_area": "kl"
}
```

### `POST /api/shortest_path`

Computes the optimal accessibility-aware route between two points.

**Request Body:**
```json
{
  "start_lat": 3.1489,
  "start_lon": 101.6957,
  "end_lat": 3.1400,
  "end_lon": 101.7000,
  "mode": "blind",
  "hour": 14,
  "area": "kl",
  "use_bidirectional": true,
  "use_dynamic_cost": true,
  "weights": {}
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start_lat` | float | — | Start latitude |
| `start_lon` | float | — | Start longitude |
| `end_lat` | float | — | End latitude |
| `end_lon` | float | — | End longitude |
| `mode` | string | `"balanced"` | Navigation mode preset |
| `hour` | int | `14` | Departure hour (0–23) |
| `area` | string | `"kl"` | Predefined area ID or `"custom"` |
| `use_bidirectional` | bool | `true` | Use bidirectional A\* (faster) |
| `use_dynamic_cost` | bool | `true` | Apply time-dependent multipliers |
| `weights` | object | `{}` | Override individual weight coefficients |

**Response:**
```json
{
  "status": "success",
  "path": [[3.1489, 101.6957], [3.1440, 101.6980], [3.1400, 101.7000]],
  "path_node_ids": [12345, 12346, 12347],
  "total_cost": 452.3,
  "static_cost": 380.1,
  "dynamic_cost": 72.2,
  "total_distance_m": 1250.5,
  "explored_count": 3420,
  "time_slot": "day",
  "algorithm": "bidirectional_a*",
  "num_nodes": 85,
  "route_analysis": {
    "total_edges": 84,
    "tactile_paving_pct": 65.0,
    "steps_count": 0,
    "lit_pct": 78.0,
    "sidewalk_pct": 72.0,
    "top_highways": [
      {"name": "footway", "pct": 45.0},
      {"name": "residential", "pct": 30.0},
      {"name": "tertiary", "pct": 15.0}
    ]
  },
  "meet_node": 12346,
  "forward_explored": 1800,
  "backward_explored": 1620
}
```

---

## Configuration

### Navigation Modes

Navigation modes are defined in `backend/config.py` under `PRESET_MODES`. Each mode specifies a `WeightCoefficients` object with custom weights for each accessibility factor. You can add your own mode:

```python
PRESET_MODES["my_mode"] = {
    "name": "My Custom Mode",
    "description": "Custom preferences...",
    "weights": WeightCoefficients(
        tactile_paving=3.0,
        steps=5.0,
        # ... other weights
    ),
}
```

### Area Definitions

Areas are configured via `AREA_CONFIGS`:

```python
AREA_CONFIGS = {
    "kl":   {"lat": 3.110, "lon": 101.686, "dist": 5000, "name": "Kuala Lumpur"},
    "singapore": {"lat": 1.352, "lon": 103.820, "dist": 3000, "name": "Singapore"},
    "tokyo": {"lat": 35.676, "lon": 139.750, "dist": 3000, "name": "Tokyo"},
    "berlin": {"lat": 52.520, "lon": 13.405, "dist": 3000, "name": "Berlin"},
}
```

You can add any city by providing its latitude, longitude, and search radius (in meters). When a user's coordinates fall outside predefined areas, the system automatically loads the surrounding region dynamically.

### Region Tag Overrides

Real-world OSM tag completeness varies by region. `REGION_TAG_OVERRIDES` in `config.py` allows per-city, per-highway-type tag defaults:

```python
REGION_TAG_OVERRIDES = {
    "kl": {
        "footway": {
            "tactile_paving": "limited",
            "lit": "yes",
            "surface": "paving_stones",
        },
        # ...
    },
    "singapore": {
        "footway": {
            "tactile_paving": "yes",
            "lit": "yes",
            "surface": "concrete",
        },
        # ...
    },
}
```

The tag filling priority is:

| Priority | Source | Description |
|----------|--------|-------------|
| 1 (Lowest) | `FALLBACK_DEFAULTS` | Global defaults for any tag |
| 2 | `HIGHWAY_TAG_DEFAULTS` | Per-road-type defaults |
| 3 | `REGION_TAG_OVERRIDES` | Regional customizations |
| 4 (Highest) | Original OSM data | Preserved via `setdefault` |

---

## Data Sources

- **[OpenStreetMap](https://www.openstreetmap.org/)** — Primary source for road networks and accessibility tags (tactile_paving, sidewalk, lit, surface, incline, width, etc.).
- **[OSMnx](https://osmnx.readthedocs.org/)** — Python library for downloading and modeling OSM street networks.
- **[MapLibre GL JS](https://maplibre.org/)** — Open-source map rendering library for the frontend.
- **[OpenFreeMap](https://openfreemap.org/)** — Free map tile service used for the "Liberty" map style (no API key required).

---

## Development

### Running Tests

```bash
pytest
```

### Linting

```bash
ruff check .
```

### Adding a New City

1. Add an entry to `AREA_CONFIGS` in `backend/config.py`:
   ```python
   "paris": {"lat": 48.8566, "lon": 2.3522, "dist": 3000, "name": "Paris"},
   ```
2. (Optional) Add region tag overrides in `REGION_TAG_OVERRIDES`.
3. Add the city to the `AREAS` array in `frontend/public/index.html`.
4. Pre-download the data:
   ```bash
   python scripts/download_osm_data.py --area paris
   ```

### Adding a New Navigation Mode

1. Add a `WeightCoefficients` entry to `PRESET_MODES` in `backend/config.py`.
2. Add the mode button to the `MODES` array in `frontend/public/index.html`.
3. Add a color and icon mapping in the `COL` dictionary and `icons` object.

---

## Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork** the repository.
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`).
3. **Commit your changes** (`git commit -m 'Add amazing feature'`).
4. **Push to the branch** (`git push origin feature/amazing-feature`).
5. **Open a Pull Request** describing your changes in detail.

Please ensure your code passes linting (`ruff check .`) and existing tests (`pytest`).

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

## Acknowledgments

- OpenStreetMap contributors for providing the foundational map data.
- The OSMnx project for making OSM data accessible in Python.
- MapLibre GL JS for enabling open-source map rendering.
- Academic research on accessibility-aware pathfinding that inspired the multi-factor cost model.

---


