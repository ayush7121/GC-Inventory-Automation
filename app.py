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
                    'Percentage item ': (t_item / total_item_all) * 100 if total_item_all else 0
                })
                
            summary_df = pd.DataFrame(summary_data)
            
            # Add the final Totals row to match their manual sheet exactly
            summary_df.loc[len(summary_df)] = {
                'Name ': 'Total Item both PL &Glow ',
                'Total SKU ': total_sku_all,
                'Total Item': total_item_all,
                'Percentage SKU ': None,
                'Percentage item ': None
            }

            # 4. Generate the Excel File
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                
                # Write the PL vs Glow Summary as the very first tab
                summary_df.to_excel(writer, sheet_name='% Stock', index=False)
                
                # Write each Category to its own tab
                categories = merged_df['Category'].unique()
                for cat in categories:
                    cat_df = merged_df[merged_df['Category'] == cat]
                    
                    # Drop our temporary 'Brand' column before saving the tab
                    cat_df = cat_df.drop(columns=['Brand']) 
                    
                    # Sort by Subcategory if it's being used
                    if 'Subcategory' in cat_df.columns:
                        cat_df = cat_df.sort_values(by=['Subcategory', 'SKU'])
                        
                    # Ensure valid Excel sheet names (max 31 chars, no forbidden symbols)
                    safe_sheet_name = str(cat)[:31].replace(':', '').replace('/', '').replace('\\', '').replace('?', '').replace('*', '').replace('[', '').replace(']', '')
                    cat_df.to_excel(writer, sheet_name=safe_sheet_name, index=False)

            output.seek(0)
            
            st.success("✅ Report Generated Successfully!")
            st.download_button(
                label="📥 Download Formatted Excel Report",
                data=output,
                file_name="Automated_Inventory_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        except Exception as e:
            st.error(f"An error occurred during processing: {e}")