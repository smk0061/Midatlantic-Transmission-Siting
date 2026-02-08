# create_grid.py
# generates 2km grid cells across study area and calculates percentage overlap
# with protected lands (GAP 1-2) and military installations.
#
# inputs: study area boundary, protected areas (GAP 1-2), military installations
# outputs: 2km grid with protected_pct and military_pct fields

import geopandas as gpd
from shapely.geometry import box
from pathlib import Path

data_dir = Path("data")
output_dir = Path("outputs")
output_dir.mkdir(exist_ok=True)

CRS = "EPSG:5070"

states = gpd.read_file(data_dir / "states" / "states-of-interest" / "AOI.shp")
protected_lands = gpd.read_file(data_dir / "protected-areas" / "gap1and2PAD" / "gap1-2PAD.shp")
if protected_lands.crs != CRS:
    protected_lands = protected_lands.to_crs(CRS)

military = gpd.read_file(data_dir / "military" / "military_areas" / "military-areas.shp")
if military.crs != CRS:
    military = military.to_crs(CRS)

print("loaded study area, protected lands, and military areas")

minx, miny, maxx, maxy = states.total_bounds
grid_size = 2000

n_cells_x = int((maxx - minx) / grid_size) + 1
n_cells_y = int((maxy - miny) / grid_size) + 1

print(f"grid dimensions: {n_cells_x} x {n_cells_y}")

grid_cells = []
cell_ids = []
cell_id = 0

for i in range(n_cells_x):
    for j in range(n_cells_y):
        cell_minx = minx + (i * grid_size)
        cell_miny = miny + (j * grid_size)
        cell_maxx = cell_minx + grid_size
        cell_maxy = cell_miny + grid_size

        cell = box(cell_minx, cell_miny, cell_maxx, cell_maxy)
        grid_cells.append(cell)
        cell_ids.append(cell_id)
        cell_id += 1

grid = gpd.GeoDataFrame({'cell_id': cell_ids}, geometry=grid_cells, crs=CRS)
print(f"created {len(grid)} cells")

grid = gpd.overlay(grid, states, how='intersection')
print(f"cells after clipping: {len(grid)}")

# calculate protected area overlap percentage
print("calculating protected area overlap")
grid['protected_pct'] = 0.0

protected_lands['geometry'] = protected_lands.geometry.buffer(0)

for idx, cell in grid.iterrows():
    cell_area = cell.geometry.area

    protected_intersect = protected_lands[protected_lands.intersects(cell.geometry)]
    if len(protected_intersect) > 0:
        overlap = protected_intersect.intersection(cell.geometry).area.sum()
        grid.at[idx, 'protected_pct'] = (overlap / cell_area) * 100

print("protected overlap calculated")

# calculate military area overlap percentage
print("calculating military area overlap")
grid['military_pct'] = 0.0

military['geometry'] = military.geometry.buffer(0)

for idx, cell in grid.iterrows():
    cell_area = cell.geometry.area

    military_intersect = military[military.intersects(cell.geometry)]
    if len(military_intersect) > 0:
        overlap = military_intersect.intersection(cell.geometry).area.sum()
        grid.at[idx, 'military_pct'] = (overlap / cell_area) * 100

print("military overlap calculated")

print(f"\nfinal grid: {len(grid)} cells")
print(f"cells with protected overlap: {len(grid[grid['protected_pct'] > 0])}")
print(f"cells with military overlap: {len(grid[grid['military_pct'] > 0])}")

grid.to_file(output_dir / "grid_2km.geojson", driver='GeoJSON')
print("grid saved")
