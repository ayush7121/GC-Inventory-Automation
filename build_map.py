import pandas as pd
import glob
import os

print("Starting Master Map generation...")

all_maps = []

# This will find all the separate category CSVs you downloaded
for file in glob.glob("*.csv"):
    # We skip the main inventory files so they don't get mixed in
    if "Main" in file or "%Stock" in file or "master_map" in file:
        continue
        
    try:
        df = pd.read_csv(file)
        
        # If the file has SKUs, we map them!
        if 'SKU' in df.columns:
            # Extract the clean category name from your specific file names
            # (e.g., "GC Inventory... - Autumn.csv" becomes "Autumn")
            category_name = file.replace('.csv', '').split(' - ')[-1].strip()
            
            # Create the 2-column map for this specific category
            temp_df = df[['SKU']].copy()
            temp_df['Category'] = category_name
            all_maps.append(temp_df)
            print(f"Mapped {len(temp_df)} SKUs for {category_name}")
            
    except Exception as e:
        print(f"Skipping {file}: {e}")

# Combine every category into one master file
if all_maps:
    master_map = pd.concat(all_maps, ignore_index=True)
    
    # Remove any duplicates just in case
    master_map = master_map.drop_duplicates(subset=['SKU'])
    
    # Save the final configuration file
    master_map.to_csv("master_map.csv", index=False)
    print(f"\n✅ SUCCESS: master_map.csv generated with {len(master_map)} total SKUs!")
else:
    print("No category CSV files found. Make sure they are in the same folder as this script.")