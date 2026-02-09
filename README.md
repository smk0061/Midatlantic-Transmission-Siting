# Mid-Atlantic Transmission Siting Analysis

A GIS-based multi-criteria decision analysis (MCDA) pipeline for identifying optimal transmission corridor routes to connect renewable generation sources to data center load growth across six Mid-Atlantic states (WV, VA, PA, MD, DE, NJ).

![Corridor Map](maps/new_corridors_map.png)

## Overview

Data center development across the Mid-Atlantic is driving unprecedented demand for grid capacity. This project identifies where new or upgraded transmission infrastructure (≥138kV) should be sited by combining least-cost path analysis with suitability scoring across environmental, infrastructure, and energy criteria.

The pipeline evaluates over 50,000 grid cells at 2km resolution, scores them against four weighted criteria with environmental constraint penalties, then routes least-cost corridors from NREL Interconnection-Ready Energy Zones (IREZ) and proposed utility-scale generation to clustered data center load hubs.

## Methodology

**Suitability Scoring (1–9 scale, lower = more suitable)**

| Criterion | Weight | Description |
|-----------|--------|-------------|
| ROW Proximity | 35% | Distance to existing transmission, roads, rail, pipelines |
| Renewable Capacity | 30% | Inverse-distance-weighted access to proposed + retired generation |
| Data Center Proximity | 25% | Distance to nearest data center facility |
| IREZ Proximity | 10% | Distance to NREL strategic renewable energy zones |

Additive penalties (0–10) applied for overlap with GAP 1–2 protected lands and military installations.

**Corridor Extraction**

Least-cost paths routed using scikit-image's `route_through_array` with 8-way connectivity from each generation source to 10 K-Means-clustered data center hubs. Corridors classified into three tiers based on cost above per-source minimum:

- **Tier 1:** 0–10% above minimum (highest priority)
- **Tier 2:** 10–20% above minimum
- **Tier 3:** 20–30% above minimum

Corridor cells further classified as **Contains_Existing** (intersects ≥138kV transmission, suitable for ROW expansion) or **New_Corridor** (greenfield).

**Transmission Upgrade Scoring**

Existing ≥138kV lines scored for upgrade priority based on accessible generation capacity within a 10km buffer, proximity to data centers, and capacity density (MW/km). Separate analyses for proposed generation (new capacity) and retired generation sites (brownfield redevelopment).

## Data Sources

| Dataset | Source |
|---------|--------|
| Power plants (operable, proposed, retired) | EIA-860 2024 |
| Transmission lines (≥138kV) | HIFLD |
| Data centers | HIFLD |
| Protected areas (GAP 1–2) | USGS PAD-US |
| Military installations | HIFLD |
| Roads & Rail | State DOT / FRA |
| Natural gas & hydrocarbon pipelines | EIA |
| IREZ zones | NREL |

## Pipeline

```
1. preprocessing/
   extract_eia_plants.py              Filter EIA-860 by fuel type, state, voltage

2. grid_scoring/
   create_grid.py                     Generate 2km grid, calculate constraint overlaps
   score_grid.py                      MCDA suitability scoring

3. corridor_extraction/
   extract_corridors.py               Least-cost path routing + tier classification
   classify_corridors.py              Label existing vs greenfield corridors

4. transmission_upgrades/
   score_upgrades.py --status proposed   Score lines for new generation capacity
   score_upgrades.py --status retired    Score lines for brownfield redevelopment
```

## Dependencies

geopandas, pandas, numpy, scikit-learn, scikit-image, shapely, openpyxl

## Author

Sean Keane
