# extract_corridors.py
# extracts optimal transmission corridor zones using least-cost path analysis
# from generation sources (IREZ + utility-scale proposed renewables) to data
# center load centers. implements per-pair 30% threshold with three priority
# tiers based on cost above minimum.
#
# methodology: converts scored grid to cost raster, routes paths using
# scikit-image route_through_array with 8-way connectivity, classifies
# corridors into tiers (0-10%, 10-20%, 20-30% above per-source minimum).
#
# inputs: scored_grid.geojson, generation sources, data centers
# outputs: corridor_zones.geojson with cost_tier field

import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.cluster import KMeans
from skimage.graph import route_through_array
from shapely.geometry import Point

data_dir = Path("data")
output_dir = Path("outputs")

CRS = "EPSG:5070"

grid = gpd.read_file(output_dir / "scored_grid.geojson")
data_centers = gpd.read_file(data_dir / "datacenters" / "datacenters-shp" / "datacenters-AOI.shp")
irez_points = gpd.read_file(data_dir / "IREZ" / "IREZ-shp" / "AOI-IREZ.shp")

wind = gpd.read_file(data_dir / "power-plants" / "power-plants-shp" / "wind-plants.shp")
solar = gpd.read_file(data_dir / "power-plants" / "power-plants-shp" / "solar-plants.shp")
hydro = gpd.read_file(data_dir / "power-plants" / "power-plants-shp" / "hydro-plants.shp")
biomass = gpd.read_file(data_dir / "power-plants" / "power-plants-shp" / "biomass-plants.shp")

renewables = pd.concat([wind, solar, hydro, biomass], ignore_index=True)
renewables = gpd.GeoDataFrame(renewables, geometry='geometry', crs=CRS)
eia_proposed = renewables[renewables['PlantStatu'] == 'Proposed'].copy()

# filter for utility-scale projects (>=20 MW threshold)
major_proposed = eia_proposed[eia_proposed['Nameplate'] >= 20].copy()

print(f"loaded {len(grid)} grid cells")
print(f"loaded {len(data_centers)} data centers")
print(f"loaded {len(irez_points)} IREZ points")
print(f"loaded {len(major_proposed)} proposed renewable plants >= 20 MW")

# cluster data centers into 10 regional load hubs
print("\nclustering data centers into 10 regional hubs")
dc_coords = np.array([[geom.x, geom.y] for geom in data_centers.geometry])
kmeans_dc = KMeans(n_clusters=10, random_state=42, n_init=10)
dc_labels = kmeans_dc.fit_predict(dc_coords)

dc_hubs = []
for i in range(10):
    cluster_coords = dc_coords[dc_labels == i]
    centroid_x = cluster_coords[:, 0].mean()
    centroid_y = cluster_coords[:, 1].mean()
    dc_hubs.append(Point(centroid_x, centroid_y))

print(f"created {len(dc_hubs)} DC hub centroids")

# combine IREZ strategic zones + utility-scale proposed plants as sources
sources = []
source_labels = []

for idx, irez in irez_points.iterrows():
    sources.append(irez.geometry)
    source_labels.append(f"IREZ_{idx}")

for idx, plant in major_proposed.iterrows():
    sources.append(plant.geometry)
    source_labels.append(f"PLANT_{idx}")

print(f"\ntotal sources: {len(sources)} ({len(irez_points)} IREZ + {len(major_proposed)} plants)")

grid['centroid'] = grid.geometry.centroid

# convert scored grid to cost raster
print("\ncreating cost surface raster")
grid_size = 2000
minx, miny, maxx, maxy = grid.total_bounds

n_cols = int((maxx - minx) / grid_size) + 1
n_rows = int((maxy - miny) / grid_size) + 1

cost_raster = np.full((n_rows, n_cols), np.inf)
cell_to_raster = {}

for idx, row in grid.iterrows():
    cell_geom = row.geometry.centroid
    col = int((cell_geom.x - minx) / grid_size)
    row_idx = n_rows - 1 - int((cell_geom.y - miny) / grid_size)

    if 0 <= row_idx < n_rows and 0 <= col < n_cols:
        cost_raster[row_idx, col] = row['final_score']
        cell_to_raster[(row_idx, col)] = row['cell_id']

print(f"cost raster shape: {cost_raster.shape}")
print(f"valid cells (not inf): {np.sum(cost_raster != np.inf)}")


def coords_to_indices(x, y, minx, miny, grid_size, n_rows, n_cols):
    """convert geographic coordinates to raster array indices."""
    col = int((x - minx) / grid_size)
    row = n_rows - 1 - int((y - miny) / grid_size)
    row = max(0, min(row, n_rows - 1))
    col = max(0, min(col, n_cols - 1))
    return row, col


print("\ncalculating least-cost paths with tiered thresholds (10%, 20%, 30%)")

tier1_cells = set()
tier2_cells = set()
tier3_cells = set()

for src_idx, (source, src_label) in enumerate(zip(sources, source_labels)):
    src_x, src_y = source.x, source.y
    start_row, start_col = coords_to_indices(src_x, src_y, minx, miny, grid_size, n_rows, n_cols)

    pair_costs = []
    pair_indices = []

    for hub_idx, hub in enumerate(dc_hubs):
        hub_x, hub_y = hub.x, hub.y
        end_row, end_col = coords_to_indices(hub_x, hub_y, minx, miny, grid_size, n_rows, n_cols)

        try:
            indices, cost = route_through_array(
                cost_raster,
                (start_row, start_col),
                (end_row, end_col),
                fully_connected=True
            )
            pair_costs.append(cost)
            pair_indices.append(indices)
        except Exception:
            pair_costs.append(np.inf)
            pair_indices.append(None)

    valid_costs = [c for c in pair_costs if c != np.inf]
    if len(valid_costs) > 0:
        min_cost = min(valid_costs)

        threshold_10 = min_cost * 1.10
        threshold_20 = min_cost * 1.20
        threshold_30 = min_cost * 1.30

        for cost, indices in zip(pair_costs, pair_indices):
            if indices is not None:
                for row_idx, col_idx in indices:
                    if (row_idx, col_idx) in cell_to_raster:
                        cell_id = cell_to_raster[(row_idx, col_idx)]

                        if cost <= threshold_10:
                            tier1_cells.add(cell_id)
                        elif cost <= threshold_20:
                            tier2_cells.add(cell_id)
                        elif cost <= threshold_30:
                            tier3_cells.add(cell_id)

        print(f"{src_label}: min={min_cost:.2f}, "
              f"T1={sum(1 for c in pair_costs if c <= threshold_10)}, "
              f"T2={sum(1 for c in pair_costs if threshold_10 < c <= threshold_20)}, "
              f"T3={sum(1 for c in pair_costs if threshold_20 < c <= threshold_30)}")

print(f"\ntier 1 cells (0-10%): {len(tier1_cells)}")
print(f"tier 2 cells (10-20%): {len(tier2_cells)}")
print(f"tier 3 cells (20-30%): {len(tier3_cells)}")

all_corridor_cells = tier1_cells | tier2_cells | tier3_cells
corridors = grid[grid['cell_id'].isin(all_corridor_cells)].copy()


def assign_tier(cell_id):
    """assign cost tier based on cell membership (best tier wins)."""
    if cell_id in tier1_cells:
        return "Tier_1"
    elif cell_id in tier2_cells:
        return "Tier_2"
    else:
        return "Tier_3"


corridors['cost_tier'] = corridors['cell_id'].apply(assign_tier)
corridors = corridors.drop(columns=['centroid'])

corridors.to_file(output_dir / "corridor_zones.geojson", driver='GeoJSON')
print("corridors saved")
