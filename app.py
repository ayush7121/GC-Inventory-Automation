import streamlit as st
import pandas as pd
import numpy as np
import io

# --- 1. PAGE SETUP ---
st.set_page_config(page_title="Weekly Inventory Automator", layout="centered")

st.title("📦 Weekly Inventory Automator")
st.write("Upload your Master Map and Monday Export to generate the automated categorized report.")

# File Uploaders
mapping_file = st.file_uploader("1. Upload Master Map (CSV or Excel)", type=['csv', 'xlsx'])
monday_file = st.file_uploader("2. Upload Monday Export (CSV)", type=['csv'])

# --- 2. REPORT GENERATION ---
if st.button("🚀 Generate Automated Report"):
    if not mapping_file or not monday_file:
        st.error("Please upload both files to proceed.")
    else:
        try:
            # 1. Read the uploaded files
            monday_df = pd.read_csv(monday_file)
            
            # Read Master Map (expecting an optional 'Subcategory' column)
            if mapping_file.name.endswith('.xlsx'):
                map_df = pd.read_excel(mapping_file, engine='calamine')
            else:
                map_df = pd.read_csv(mapping_file)

            # --- BULLETPROOFING: Strip accidental spaces from column names ---
            monday_df.columns = monday_df.columns.str.strip()
            map_df.columns = map_df.columns.str.strip()
            # -----------------------------------------------------------------

            # 2. Merge Data
            merged_df = pd.merge(monday_df, map_df, on='SKU', how='left')
            
            # Fill missing categories with 'Uncategorized'
            merged_df['Category'] = merged_df['Category'].fillna('Uncategorized')
            
            # If Subcategory exists in map, fill missing with blanks, otherwise create an empty column
            if 'Subcategory' in map_df.columns:
                merged_df['Subcategory'] = merged_df['Subcategory'].fillna('')
            else:
                merged_df['Subcategory'] = ''

            # 3. Calculate PL vs Glow (% Stock Summary)
            # Identify 'Glow' by checking the Inventory Name; default everything else to 'PL'
            merged_df['Brand'] = np.where(merged_df['Inventory Name'].str.contains('Glow', case=False, na=False), 'Glow ', 'PL')
            
            total_sku_all = merged_df['SKU'].nunique()
            total_item_all = merged_df['On Hand'].sum()
            
            summary_data = []
            for brand in ['PL', 'Glow ']:
                brand_df = merged_df[merged_df['Brand'] == brand]
                t_sku = brand_df['SKU'].nunique()
                t_item = brand_df['On Hand'].sum()
                
                summary_data.append({
                    'Name ': brand,
                    'Total SKU ': t_sku,
                    'Total Item': t_item,
                    'Percentage SKU ': (t_sku / total_sku_all) * 100 if total_sku_all else 0,
                    'Percentage item ':
