import streamlit as st
import pandas as pd
import io

# --- 1. PAGE SETUP ---
st.set_page_config(page_title="Weekly Inventory Automator", layout="centered")
st.title("📦 Weekly Inventory Automator")

# --- CREATE TABS FOR CLEAN UI ---
tab1, tab2 = st.tabs(["📊 Generate Weekly Report", "🛠️ Build Master Map"])

# ==========================================
# TAB 1: THE MAIN INVENTORY AUTOMATOR
# ==========================================
with tab1:
    st.write("Upload your master mapping file and the raw Monday export to instantly generate the formatted weekly report.")

    # --- FILE UPLOADERS ---
    col1, col2 = st.columns(2)
    with col1:
        mapping_file = st.file_uploader("1. Upload Master Category Map (Excel/CSV)", type=["xlsx", "csv"], key="map_upload")
    with col2:
        # FIXED: Box 2 now accepts both CSV and Excel files
        raw_file = st.file_uploader("2. Upload Raw Monday Export (Excel/CSV)", type=["xlsx", "csv"], key="raw_upload")

    # --- CORE PROCESSING LOGIC ---
    def process_inventory(raw_df, map_df):
        numeric_cols = ['Incoming', 'On Hand', 'Committed', 'Fulfillable', 'Exception', 'Sellable', 'Backordered', 'Internal Transfer']
        
        # --- BULLETPROOFING: Strip accidental spaces from Headers ---
        raw_df.columns = raw_df.columns.str.strip()
        if map_df is not None:
            map_df.columns = map_df.columns.str.strip()

        for col in numeric_cols:
            if col in raw_df.columns:
                raw_df[col] = pd.to_numeric(raw_df[col], errors='coerce').fillna(0)

        # Map SKUs to Categories
        if map_df is not None and 'SKU' in map_df.columns and 'Category' in map_df.columns:
            # --- BULLETPROOFING: Strip hidden spaces from the actual SKUs ---
            map_df['SKU'] = map_df['SKU'].astype(str).str.strip()
            raw_df['SKU'] = raw_df['SKU'].astype(str).str.strip()
            
            sku_to_category = dict(zip(map_df['SKU'], map_df['Category']))
            raw_df['Category'] = raw_df['SKU'].map(sku_to_category).fillna('Uncategorized')
        else:
            raw_df['Category'] = 'Uncategorized'

        # Differentiate PL vs Glow
        raw_df['is_glow'] = raw_df['Inventory Name'].str.contains('Glow', case=False, na=False)

        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            
            # --- A. Build Summary Sheet (%Stock) ---
            mapped_df = raw_df[raw_df['Category'] != 'Uncategorized']
            pl_data = mapped_df[~mapped_df['is_glow']]
            glow_data = mapped_df[mapped_df['is_glow']]
            
            total_sku_count = mapped_df['SKU'].nunique()
            total_sellable_sum = mapped_df['Sellable'].sum()
            
            summary_df = pd.DataFrame([
                {'Name': 'PL', 'Total SKU': pl_data['SKU'].nunique(), 'Total Item': pl_data['Sellable'].sum(), 
                 'Percentage SKU': (pl_data['SKU'].nunique() / total_sku_count * 100) if total_sku_count > 0 else 0,
                 'Percentage item': (pl_data['Sellable'].sum() / total_sellable_sum * 100) if total_sellable_sum > 0 else 0},
                {'Name': 'Glow', 'Total SKU': glow_data['SKU'].nunique(), 'Total Item': glow_data['Sellable'].sum(),
                 'Percentage SKU': (glow_data['SKU'].nunique() / total_sku_count * 100) if total_sku_count > 0 else 0,
                 'Percentage item': (glow_data['Sellable'].sum() / total_sellable_sum * 100) if total_sellable_sum > 0 else 0},
                {'Name': 'Total Item both PL & Glow', 'Total SKU': total_sku_count, 'Total Item': total_sellable_sum,
                 'Percentage SKU': 100.0, 'Percentage item': 100.0}
            ])
            summary_df.to_excel(writer, sheet_name='%Stock', index=False)

            # --- B. Build Categorized Sheets ---
            cols = ['SKU', 'Inventory ID', 'Inventory Name', 'Lot Number', 'Expiration Date', 'Incoming', 'On Hand', 'Committed', 'Fulfillable', 'Exception', 'Sellable', 'Backordered', 'Internal Transfer', 'Fulfillment Center']
            cols = [c for c in cols if c in raw_df.columns] 
            
            categories = sorted(raw_df['Category'].unique())
            for cat in categories:
                df_cat = raw_df[raw_df['Category'] == cat].copy()
                df_cat = df_cat.sort_values(by='Sellable', ascending=False)
                df_display = df_cat[cols]
                
                # Calculate Bold Totals Row
                total_row_data = {col: df_display[col].sum() if col in numeric_cols else "" for col in cols}
                total_row_data['SKU'] = 'TOTAL'
                total_row_data['Inventory Name'] = f'Category Total: {cat}'
                
                df_final_cat = pd.concat([df_display, pd.DataFrame([total_row_data])], ignore_index=True)
                
                safe_sheet_name = str(cat)[:31].replace(':', '').replace('/', '').replace('\\', '').replace('?', '').replace('*', '').replace('[', '').replace(']', '')
                df_final_cat.to_excel(writer, sheet_name=safe_sheet_name, index=False)

        return output.getvalue(), total_sellable_sum, len(raw_df[raw_df['Category'] == 'Uncategorized'])

    # --- EXECUTION BUTTON ---
    if mapping_file and raw_file:
        if st.button("🚀 Generate Automated Report", use_container_width=True):
            with st.spinner("Sorting SKUs and calculating totals..."):
                
                # FIXED: Pandas will automatically use read_excel if the file is an xlsx
                map_df = pd.read_excel(mapping_file) if mapping_file.name.endswith(('.xlsx', '.xls')) else pd.read_csv(mapping_file)
                raw_df = pd.read_excel(raw_file) if raw_file.name.endswith(('.xlsx', '.xls')) else pd.read_csv(raw_file)
                
                excel_data, total_items, uncategorized_count = process_inventory(raw_df, map_df)
                
                st.success("Report Generated Successfully!")
                col3, col4 = st.columns(2)
                col3.metric(label="Total Sellable Items", value=f"{total_items:,.0f}")
                col4.metric(label="New/Uncategorized SKUs Found", value=uncategorized_count, delta_color="inverse")
                
                if uncategorized_count > 0:
                    st.warning(f"⚠️ {uncategorized_count} SKUs were moved to the 'Uncategorized' tab. Please check them.")

                st.download_button(
                    label="📥 Download Formatted Excel Report",
                    data=excel_data,
                    file_name="Automated_Weekly_Inventory.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

# ==========================================
# TAB 2: THE MASTER MAP BUILDER
# ==========================================
with tab2:
    st.header("🛠️ Master Map Builder")
    st.write("Drag and drop all your individual category files here. The system will automatically stitch them together into a perfect `master_map.csv`.")
    
    # FIXED: Map Builder now accepts both CSV and Excel category files
    category_files = st.file_uploader("Upload Category Files (Excel/CSV)", type=["csv", "xlsx"], accept_multiple_files=True, key="cat_upload")
    
    if st.button("🏗️ Build Master Map", use_container_width=True):
        if category_files:
            all_maps = []
            with st.spinner("Extracting SKUs and building map..."):
                for file in category_files:
                    if "Main" in file.name or "%Stock" in file.name or "master_map" in file.name:
                        continue
                    
                    try:
                        # FIXED: Pandas reads Excel or CSV safely for the builder
                        df = pd.read_excel(file) if file.name.endswith(('.xlsx', '.xls')) else pd.read_csv(file)
                        df.columns = df.columns.str.strip()
                        
                        if 'SKU' in df.columns:
                            df['SKU'] = df['SKU'].astype(str).str.strip()
                            # Clean the file extension off the category name whether it is .csv or .xlsx
                            category_name = file.name.replace('.csv', '').replace('.xlsx', '').split(' - ')[-1].strip()
                            
                            temp_df = df[['SKU']].copy()
                            temp_df['Category'] = category_name
                            all_maps.append(temp_df)
                    except Exception as e:
                        st.error(f"Error reading {file.name}: {e}")
            
            if all_maps:
                master_map = pd.concat(all_maps, ignore_index=True)
                master_map = master_map.drop_duplicates(subset=['SKU'])
                
                csv_buffer = master_map.to_csv(index=False).encode('utf-8')
                
                st.success(f"✅ Map successfully built! Found {len(master_map)} unique SKUs across {len(all_maps)} categories.")
                
                st.download_button(
                    label="📥 Download master_map.csv",
                    data=csv_buffer,
                    file_name="master_map.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.error("Could not find any 'SKU' columns in the uploaded files. Please check your files.")
        else:
            st.warning("Please upload at least one category file to build the map.")