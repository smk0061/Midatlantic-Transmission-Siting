# score_upgrades.py
# scores existing transmission lines for upgrade priority based on either
# proposed generation capacity or retired generation sites (brownfield
# redevelopment). evaluates which >=138kV lines should be upgraded to
# accommodate new or replacement generation projects.
#
# scoring: 1-9 scale where lower = higher upgrade priority
# weights: accessible capacity 50%, DC proximity 30%, capacity density 20%
# buffer: 10km radius for accessible capacity calculation
#
# usage:
#   python score_upgrades.py --status proposed
#   python score_upgrades.py --status retired
#
# inputs: existing transmission >=138kV, power plants (all fuel types), data centers
# outputs: transmission_upgrades_{status}.geojson with upgrade_score field

import argparse
import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path

data_dir = Path("data")
output_dir = Path("outputs")

CRS = "EPSG:5070"


def score_transmission_upgrades(status):
    """score transmission lines for upgrade priority by plant status."""

    transmission = gpd.read_file(data_dir / "transmission-lines" / "aoi-transmission-lines-shp" / "AOI-transmission-lines-138kv.shp").to_crs(CRS)
    data_centers = gpd.read_file(data_dir / "datacenters" / "datacenters-shp" / "datacenters-AOI.shp")

    # load all fuel types
    fuel_files = ['wind', 'solar', 'hydro', 'biomass', 'coal', 'gas', 'nuclear', 'oil', 'battery']
    plant_frames = []
    for fuel in fuel_files:
        gdf = gpd.read_file(data_dir / "power-plants" / "power-plants-shp" / f"{fuel}-plants.shp")
        plant_frames.append(gdf)

    all_plants = pd.concat(plant_frames, ignore_index=True)
    all_plants = gpd.GeoDataFrame(all_plants, geometry='geometry', crs=CRS)

    target_plants = all_plants[all_plants['PlantStatu'] == status.capitalize()].copy()

    print(f"loaded {len(transmission)} transmission lines")
    print(f"loaded {len(target_plants)} {status} plants (all fuel types)")
    print(f"loaded {len(data_centers)} data centers")

    transmission['length_km'] = transmission.geometry.length / 1000

    # calculate accessible capacity within 10km buffer
    print("\ncalculating accessible capacity within 10km buffer")

    def calc_accessible_capacity(line_geom):
        buffer = line_geom.buffer(10000)
        nearby_plants = target_plants[target_plants.geometry.within(buffer)]
        return nearby_plants['Nameplate'].sum()

    transmission['accessible_mw'] = transmission.geometry.apply(calc_accessible_capacity)

    # calculate distance to nearest data center
    print("calculating distance to nearest data center")

    def calc_dc_distance(line_geom):
        line_centroid = line_geom.centroid
        return data_centers.geometry.distance(line_centroid).min()

    transmission['dist_dc'] = transmission.geometry.apply(calc_dc_distance)

    # calculate capacity density
    print("calculating capacity per kilometer")
    transmission['mw_per_km'] = transmission['accessible_mw'] / transmission['length_km']
    transmission['mw_per_km'] = transmission['mw_per_km'].replace([np.inf, -np.inf], 0)

    # score transmission lines
    print("\nscoring transmission lines")

    def score_capacity(mw):
        if mw >= 500: return 1
        elif mw >= 200: return 3
        elif mw >= 50: return 6
        elif mw > 0: return 8
        else: return 9

    transmission['score_capacity'] = transmission['accessible_mw'].apply(score_capacity)

    def score_dc_dist(dist):
        if dist <= 50000: return 1
        elif dist <= 100000: return 3
        elif dist <= 200000: return 6
        else: return 9

    transmission['score_dc'] = transmission['dist_dc'].apply(score_dc_dist)

    def score_density(mw_per_km):
        if mw_per_km >= 50: return 1
        elif mw_per_km >= 20: return 3
        elif mw_per_km >= 5: return 6
        elif mw_per_km > 0: return 8
        else: return 9

    transmission['score_density'] = transmission['mw_per_km'].apply(score_density)

    weights = {
        'capacity': 0.50,
        'dc': 0.30,
        'density': 0.20
    }

    transmission['upgrade_score'] = (
        transmission['score_capacity'] * weights['capacity'] +
        transmission['score_dc'] * weights['dc'] +
        transmission['score_density'] * weights['density']
    )

    transmission = transmission.sort_values('upgrade_score')

    print(f"\nscoring complete")
    print(f"best upgrade score: {transmission['upgrade_score'].min():.2f}")
    print(f"worst upgrade score: {transmission['upgrade_score'].max():.2f}")
    print(f"lines with accessible capacity > 0: {len(transmission[transmission['accessible_mw'] > 0])}")

    output_file = output_dir / f"transmission_upgrades_{status}.geojson"
    transmission.to_file(output_file, driver='GeoJSON')
    print(f"transmission upgrade analysis saved to {output_file.name}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Score transmission lines for upgrade priority')
    parser.add_argument('--status', required=True, choices=['proposed', 'retired'],
                        help='Plant status to evaluate (proposed or retired)')
    args = parser.parse_args()

    score_transmission_upgrades(args.status)
