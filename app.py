import streamlit as st
import pandas as pd
import io

# --- 1. PAGE SETUP ---
st.set_page_config(page_title="Weekly Inventory Automator", layout="centered")
st.title("📦 Weekly Inventory Automator")
st.write("Upload your master mapping file and the raw Monday export to instantly generate the formatted weekly report.")

# --- 2. FILE UPLOADERS ---
col1, col2 = st.columns(2)
with col1:
    mapping_file = st.file_uploader("1. Upload Master Category Map (Excel/CSV)", type=["xlsx", "csv"])
with col2:
    raw_file = st.file_uploader("2. Upload Raw Monday Export (CSV)", type=["csv"])

# --- 3. CORE PROCESSING LOGIC ---
def process_inventory(raw_df, map_df):
    # Standardize numeric columns
    numeric_cols = ['Incoming', 'On Hand', 'Committed', 'Fulfillable', 'Exception', 'Sellable', 'Backordered', 'Internal Transfer']
    for col in numeric_cols:
        if col in raw_df.columns:
            raw_df[col] = pd.to_numeric(raw_df[col], errors='coerce').fillna(0)

    # Map SKUs to Categories
    if map_df is not None and 'SKU' in map_df.columns and 'Category' in map_df.columns:
        sku_to_category = dict(zip(map_df['SKU'], map_df['Category']))
        raw_df['Category'] = raw_df['SKU'].map(sku_to_category).fillna('Uncategorized')
    else:
        raw_df['Category'] = 'Uncategorized'

    # Differentiate PL vs Glow
    raw_df['is_glow'] = raw_df['Inventory Name'].str.contains('Glow', case=False, na=False)

    # Create Excel file in memory (no server storage needed)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        
        # --- A. Build Summary Sheet (%Stock) ---
        pl_data = raw_df[~raw_df['is_glow']]
        glow_data = raw_df[raw_df['is_glow']]
        total_sku_count = raw_df['SKU'].nunique()
        total_sellable_sum = raw_df['Sellable'].sum()
        
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
        cols = [c for c in cols if c in raw_df.columns] # Ensure columns exist
        
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
            df_final_cat.to_excel(writer, sheet_name=str(cat)[:31], index=False)

    return output.getvalue(), total_sellable_sum, len(raw_df[raw_df['Category'] == 'Uncategorized'])

# --- 4. EXECUTION BUTTON ---
if mapping_file and raw_file:
    if st.button("🚀 Generate Automated Report", use_container_width=True):
        with st.spinner("Sorting SKUs and calculating totals..."):
            
            # Read uploaded files
            map_df = pd.read_excel(mapping_file) if mapping_file.name.endswith('.xlsx') else pd.read_csv(mapping_file)
            raw_df = pd.read_csv(raw_file)
            
            # Process data
            excel_data, total_items, uncategorized_count = process_inventory(raw_df, map_df)
            
            # Display Success Metrics
            st.success("Report Generated Successfully!")
            col3, col4 = st.columns(2)
            col3.metric(label="Total Sellable Items", value=f"{total_items:,.0f}")
            col4.metric(label="New/Uncategorized SKUs Found", value=uncategorized_count, delta_color="inverse")
            
            if uncategorized_count > 0:
                st.warning(f"⚠️ {uncategorized_count} SKUs were moved to the 'Uncategorized' tab. Please check them.")

            # Download Button
            st.download_button(
                label="📥 Download Formatted Excel Report",
                data=excel_data,
                file_name="Automated_Weekly_Inventory.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )