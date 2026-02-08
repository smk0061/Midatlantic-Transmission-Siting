# classify_corridors.py
# classifies extracted corridor cells by infrastructure presence. labels cells
# that intersect existing >=138kV transmission as containing existing
# infrastructure (potential ROW expansion) vs new greenfield corridors.
#
# inputs: corridor_zones.geojson, existing transmission lines
# outputs: corridors_classified.geojson with infra_type field

import geopandas as gpd
from pathlib import Path

data_dir = Path("data")
output_dir = Path("outputs")

corridors = gpd.read_file(output_dir / "corridor_zones.geojson")
transmission = gpd.read_file(data_dir / "transmission-lines" / "aoi-transmission-lines-shp" / "AOI-transmission-lines-138kv.shp")

print(f"loaded {len(corridors)} corridor cells")

corridors['infra_type'] = 'New_Corridor'

for idx, cell in corridors.iterrows():
    if transmission.intersects(cell.geometry).any():
        corridors.at[idx, 'infra_type'] = 'Contains_Existing'

print(f"contains existing: {len(corridors[corridors['infra_type'] == 'Contains_Existing'])}")
print(f"new corridor: {len(corridors[corridors['infra_type'] == 'New_Corridor'])}")

corridors.to_file(output_dir / "corridors_classified.geojson", driver='GeoJSON')
print("classified corridors saved")
