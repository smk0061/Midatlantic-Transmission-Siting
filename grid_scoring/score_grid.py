# score_grid.py
# scores grid cells using multi-criteria decision analysis (MCDA) for transmission
# corridor suitability. combines four weighted criteria (renewable capacity
# accessibility, data center proximity, ROW proximity, IREZ zones) with penalties
# for protected/military land overlap.
#
# scoring: 1-9 scale where lower = more suitable
# weights: renewable capacity 30%, ROW proximity 35%, data center proximity 25%, IREZ 10%
# penalties: 0-10 based on % overlap with protected/military areas
#
# inputs: grid_2km.geojson, infrastructure layers, generation data
# outputs: scored_grid.geojson with final_score field

import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path

data_dir = Path("data")
output_dir = Path("outputs")

CRS = "EPSG:5070"

grid = gpd.read_file(output_dir / "grid_2km.geojson")
print(f"loaded grid: {len(grid)} cells")

transmission = gpd.read_file(data_dir / "transmission-lines" / "aoi-transmission-lines-shp" / "AOI-transmission-lines-138kv.shp").to_crs(CRS)
roads = gpd.read_file(data_dir / "roads" / "roads-of-interest" / "roads-AOI.shp").to_crs(CRS)
rail = gpd.read_file(data_dir / "rails" / "rails-of-interest" / "rails-AOI.shp").to_crs(CRS)
gas_pipelines = gpd.read_file(data_dir / "pipelines" / "natural_gas" / "naturalgas-pipelines.shp").to_crs(CRS)
hydrocarbon_pipelines = gpd.read_file(data_dir / "pipelines" / "hydrocarbon_pipelines" / "hydrocarbon-pipelines.shp").to_crs(CRS)
data_centers = gpd.read_file(data_dir / "datacenters" / "datacenters-shp" / "datacenters-AOI.shp").to_crs(CRS)
irez_points = gpd.read_file(data_dir / "IREZ" / "IREZ-shp" / "AOI-IREZ.shp").to_crs(CRS)

wind = gpd.read_file(data_dir / "power-plants" / "power-plants-shp" / "wind-plants.shp")
solar = gpd.read_file(data_dir / "power-plants" / "power-plants-shp" / "solar-plants.shp")
hydro = gpd.read_file(data_dir / "power-plants" / "power-plants-shp" / "hydro-plants.shp")
biomass = gpd.read_file(data_dir / "power-plants" / "power-plants-shp" / "biomass-plants.shp")

renewables = pd.concat([wind, solar, hydro, biomass], ignore_index=True)
renewables = gpd.GeoDataFrame(renewables, geometry='geometry', crs=CRS)

eia_proposed = renewables[renewables['PlantStatu'] == 'Proposed'].copy()
eia_retired = renewables[renewables['PlantStatu'] == 'Retired'].copy()

print(f"loaded {len(eia_proposed)} proposed renewable plants")
print(f"loaded {len(eia_retired)} retired renewable plants")
print(f"loaded {len(data_centers)} data centers")
print(f"loaded {len(irez_points)} IREZ points")

grid['centroid'] = grid.geometry.centroid

# score data center proximity
print("scoring: data center proximity")

def score_distance_dc(dist):
    if dist <= 50000: return 1      # <50km
    elif dist <= 100000: return 3   # 50-100km
    elif dist <= 200000: return 6   # 100-200km
    else: return 9                  # >200km

grid['dist_dc'] = grid['centroid'].apply(
    lambda x: data_centers.geometry.distance(x).min()
)
grid['score_dc'] = grid['dist_dc'].apply(score_distance_dc)

# score ROW proximity (transmission, roads, rail, pipelines)
print("scoring: ROW proximity")

row_combined = pd.concat([
    transmission.geometry,
    roads.geometry,
    rail.geometry,
    gas_pipelines.geometry,
    hydrocarbon_pipelines.geometry
])
row_geom = gpd.GeoSeries(row_combined, crs=CRS)

def score_distance_row(dist):
    if dist <= 1000: return 1       # <1km
    elif dist <= 5000: return 3     # 1-5km
    elif dist <= 10000: return 6    # 5-10km
    else: return 9                  # >10km

grid['dist_row'] = grid['centroid'].apply(
    lambda x: row_geom.distance(x).min()
)
grid['score_row'] = grid['dist_row'].apply(score_distance_row)

# score renewable capacity accessibility
# uses inverse distance weighting for proposed + retired plants
print("scoring: renewable capacity accessibility")

renewables_all = pd.concat([eia_proposed, eia_retired], ignore_index=True)

def calc_weighted_capacity(centroid):
    distances = renewables_all.geometry.distance(centroid)
    distances = distances.replace(0, 1)
    weights = 1 / distances
    weighted_cap = (renewables_all['Nameplate'] * weights).sum()
    return weighted_cap

grid['weighted_capacity'] = grid['centroid'].apply(calc_weighted_capacity)

def score_capacity(cap):
    if cap >= 0.5: return 1
    elif cap >= 0.1: return 3
    elif cap >= 0.01: return 6
    else: return 9

grid['score_renewable'] = grid['weighted_capacity'].apply(score_capacity)

# score IREZ strategic zone proximity
print("scoring: IREZ proximity")

def score_distance_irez(dist):
    if dist <= 10000: return 1      # <10km
    elif dist <= 25000: return 3    # 10-25km
    elif dist <= 50000: return 6    # 25-50km
    else: return 9                  # >50km

grid['dist_irez'] = grid['centroid'].apply(
    lambda x: irez_points.geometry.distance(x).min()
)
grid['score_irez'] = grid['dist_irez'].apply(score_distance_irez)

# calculate penalties for protected/military overlap
print("calculating protected area penalties")

def calc_protected_penalty(pct):
    if pct >= 75: return 10
    elif pct >= 50: return 6
    elif pct >= 25: return 4
    elif pct > 0: return 2
    else: return 0

grid['penalty_protected'] = grid['protected_pct'].apply(calc_protected_penalty)

print("calculating military area penalties")

def calc_military_penalty(pct):
    if pct >= 75: return 10
    elif pct >= 50: return 6
    elif pct >= 25: return 4
    elif pct > 0: return 2
    else: return 0

grid['penalty_military'] = grid['military_pct'].apply(calc_military_penalty)

# calculate final suitability score
print("calculating final scores")

weights = {
    'renewable': 0.30,
    'dc': 0.25,
    'row': 0.35,
    'irez': 0.10
}

grid['final_score'] = (
    grid['score_renewable'] * weights['renewable'] +
    grid['score_dc'] * weights['dc'] +
    grid['score_row'] * weights['row'] +
    grid['score_irez'] * weights['irez'] +
    grid['penalty_protected'] +
    grid['penalty_military']
)

grid = grid.sort_values('final_score')

print(f"scoring complete")
print(f"best score: {grid['final_score'].min():.2f}")
print(f"worst score: {grid['final_score'].max():.2f}")

grid = grid.drop(columns=['centroid'])

grid.to_file(output_dir / "scored_grid.geojson", driver='GeoJSON')
print("scored grid saved")
