# extract_eia_plants.py
# filters EIA-860 power plant data by fuel type and operational status for study
# area. extracts operable, proposed, and retired plants with transmission-level
# interconnection (>=138kV for operable/proposed, no filter for retired).
#
# inputs: EIA-860 generator and plant excel files
# outputs: per-fuel-type CSV files with plant-level aggregated capacity

import pandas as pd
from pathlib import Path

data_dir = Path("data/power-plants/eia8602024")
output_dir = Path("data/power-plants")

states = ['WV', 'VA', 'PA', 'MD', 'DE', 'NJ']

# fuel type definitions using EIA energy source codes
fuel_types = {
    'wind': ['WND'],
    'solar': ['SUN'],
    'hydro': ['WAT'],
    'biomass': ['AB', 'MSW', 'OBS', 'WDS', 'OBL', 'SLW', 'BLQ', 'WDL', 'LFG', 'OBG'],
    'coal': ['ANT', 'BIT', 'LIG', 'SGC', 'SUB', 'WC', 'RC'],
    'gas': ['BFG', 'NG', 'H2', 'OG'],
    'nuclear': ['NUC'],
    'oil': ['DFO', 'JF', 'KER', 'PC', 'PG', 'RFO', 'SGP', 'WO'],
    'geothermal': ['GEO'],
    'battery': ['MWH']
}


def extract_fuel_type(fuel_name, fuel_codes, gen_operable, gen_proposed, gen_retired_all, plants):
    """extract and aggregate plants for a specific fuel type."""

    # filter operable plants
    fuel_operable = gen_operable[
        (gen_operable['State'].isin(states)) &
        (gen_operable['Energy Source 1'].isin(fuel_codes))
    ].copy()
    fuel_operable['PlantStatus'] = 'Operable'

    # filter proposed plants
    fuel_proposed = gen_proposed[
        (gen_proposed['State'].isin(states)) &
        (gen_proposed['Energy Source 1'].isin(fuel_codes))
    ].copy()
    fuel_proposed['PlantStatus'] = 'Proposed'

    # filter retired plants only (exclude canceled)
    fuel_retired = gen_retired_all[
        (gen_retired_all['State'].isin(states)) &
        (gen_retired_all['Energy Source 1'].isin(fuel_codes)) &
        (gen_retired_all['Status'] == 'RE')
    ].copy()
    fuel_retired['PlantStatus'] = 'Retired'

    # combine all statuses
    fuel_all = pd.concat([fuel_operable, fuel_proposed, fuel_retired],
                         ignore_index=True)

    if len(fuel_all) == 0:
        print(f"{fuel_name}: no plants found")
        return None

    # aggregate capacity by plant
    capacity_by_plant = fuel_all.groupby('Plant Code').agg({
        'Nameplate Capacity (MW)': 'sum',
        'PlantStatus': 'first'
    }).reset_index()

    # merge with plant location data
    plant_codes = fuel_all['Plant Code'].unique()
    fuel_plants = plants[plants['Plant Code'].isin(plant_codes)]
    fuel_plants = fuel_plants.merge(capacity_by_plant, on='Plant Code', how='left')

    # select output columns
    fuel_final = fuel_plants[[
        'Plant Code', 'Plant Name', 'State', 'County',
        'Latitude', 'Longitude', 'Grid Voltage (kV)',
        'Nameplate Capacity (MW)', 'PlantStatus'
    ]].copy()

    # convert voltage to numeric
    fuel_final['Grid Voltage (kV)'] = pd.to_numeric(
        fuel_final['Grid Voltage (kV)'], errors='coerce'
    )

    # voltage filter: >=138kV for operable/proposed, no filter for retired
    fuel_final = fuel_final[
        ((fuel_final['PlantStatus'].isin(['Operable', 'Proposed'])) &
         (fuel_final['Grid Voltage (kV)'] >= 138)) |
        (fuel_final['PlantStatus'] == 'Retired')
    ]

    # save to CSV
    output_file = output_dir / f"{fuel_name}_plants_all.csv"
    fuel_final.to_csv(output_file, index=False)

    print(f"{fuel_name}: {len(fuel_final)} plants total")
    print(fuel_final.groupby('PlantStatus').size())
    print()

    return fuel_final


if __name__ == '__main__':
    print(f"extracting EIA-860 plant data for {len(states)} states")
    print(f"study area: {', '.join(states)}\n")

    # load EIA data once
    gen_operable = pd.read_excel(data_dir / "3_1_Generator_Y2024.xlsx",
                                 sheet_name="Operable", skiprows=1)
    gen_proposed = pd.read_excel(data_dir / "3_1_Generator_Y2024.xlsx",
                                 sheet_name="Proposed", skiprows=1)
    gen_retired_all = pd.read_excel(data_dir / "3_1_Generator_Y2024.xlsx",
                                    sheet_name="Retired and Canceled", skiprows=1)
    plants = pd.read_excel(data_dir / "2___Plant_Y2024.xlsx",
                           sheet_name="Plant", skiprows=1)

    for fuel_name, fuel_codes in fuel_types.items():
        extract_fuel_type(fuel_name, fuel_codes, gen_operable, gen_proposed,
                          gen_retired_all, plants)

    print("extraction complete")
