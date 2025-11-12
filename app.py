
import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import io
import requests

# Constants
CUSTOMER_TYPES = ['IND_OEM', 'MOB_OEM', 'JOBBER', 'USER', 'TP']
CUSTOMER_SIZES = ['HUGE', 'LARGE', 'MED', 'SMALL', 'TINY']
MINIMUM_MARGINS = {'IND_OEM': 35, 'MOB_OEM': 28, 'JOBBER': 40, 'USER': 35, 'TP': 42}
SIZE_OFFSETS = {'HUGE': 0, 'LARGE': 2, 'MED': 4, 'SMALL': 6, 'TINY': 8}

@st.cache_data
def fetch_data_from_json_url(snum, datestart, dateend):
    base_url = "https://g21.ifpusa.com/g21/ai_json.py?data=order_history"
    url = f"{base_url}&snum={snum}&datestart={datestart}&dateend={dateend}"
    response = requests.get(url)
    response.raise_for_status()
    df = pd.DataFrame(response.json())
    df = df[df['Sell Price'].notna() & (df['Sell Price'] >= 0)]
    df = df[df['Item Cost'].notna() & (df['Item Cost'] >= 0)]
    df = df[df['price_library_id'].notna()]
    df[['Customer Type', 'Customer Size']] = df['price_library_id'].str.extract(r'^(.*?)_(HUGE|LARGE|MED|SMALL|TINY)$')
    df['Margin %'] = ((df['Sell Price'] - df['Item Cost']) / df['Sell Price']) * 100
    df['Sales Discount Group'] = df['Sales Discount Group'].astype(str)
    return df

def get_ideal_margin_matrix():
    matrix = pd.DataFrame(index=CUSTOMER_TYPES, columns=CUSTOMER_SIZES)
    for ctype in CUSTOMER_TYPES:
        for csize in CUSTOMER_SIZES:
            matrix.loc[ctype, csize] = MINIMUM_MARGINS[ctype] + SIZE_OFFSETS[csize]
    return matrix.astype(float)

def plot_heatmap(data, title):
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(data, annot=True, fmt=".2f", cmap="coolwarm", linewidths=0.5, ax=ax)
    ax.set_title(title)
    return fig

st.title("📊 Live Supplier Margin Analyzer (JSON Source)")

snum = st.text_input("Enter Supplier ID (`snum`)", value="21091")
datestart = st.text_input("Enter Start Date (`datestart`, MM/DD/YYYY)", value="01/01/2025")
dateend = st.text_input("Enter End Date (`dateend`, MM/DD/YYYY)", value="11/01/2025")

if st.button("Fetch and Analyze Data"):
    try:
        df = fetch_data_from_json_url(snum, datestart, dateend)
        suppliers = sorted(df['Supplier Name'].unique())
        suppliers_dropdown = ['ALL'] + suppliers
        selected_supplier = st.selectbox("Select Supplier", suppliers_dropdown)

        exclude_misc = st.checkbox("Exclude Sales Discount Groups starting or ending with 'Z'", value=True)

        data = df.copy()
        if exclude_misc:
            data = data[~data['Sales Discount Group'].str.startswith('Z')]
            data = data[~data['Sales Discount Group'].str.endswith('Z')]

        if selected_supplier != 'ALL':
            data = data[data['Supplier Name'] == selected_supplier]

        if data.empty:
            st.warning("No data available after filtering.")
        else:
            st.subheader(f"📊 {'Global' if selected_supplier == 'ALL' else 'Supplier'}-Level Summary Heatmaps")
            actual_all = data.pivot_table(values='Margin %', index='Customer Type', columns='Customer Size', aggfunc='mean')
            actual_all = actual_all.reindex(index=CUSTOMER_TYPES, columns=CUSTOMER_SIZES)
            ideal_all = get_ideal_margin_matrix()
            diff_all = actual_all - ideal_all

            st.pyplot(plot_heatmap(actual_all, f"SUMMARY: Actual Margins - {selected_supplier}"))
            st.pyplot(plot_heatmap(ideal_all, f"SUMMARY: Ideal Margins - {selected_supplier}"))
            st.pyplot(plot_heatmap(diff_all, f"SUMMARY: Difference Margins - {selected_supplier}"))

            if selected_supplier != 'ALL':
                st.subheader("📊 Sales Discount Group Heatmaps")
                group_options = sorted(data['Sales Discount Group'].unique())
                for group in group_options:
                    sub = data[data['Sales Discount Group'] == group]
                    actual = sub.pivot_table(values='Margin %', index='Customer Type', columns='Customer Size', aggfunc='mean')
                    actual = actual.reindex(index=CUSTOMER_TYPES, columns=CUSTOMER_SIZES)
                    ideal = get_ideal_margin_matrix()
                    difference = actual - ideal

                    st.pyplot(plot_heatmap(actual, f"Actual Margins - {selected_supplier} | Group {group}"))
                    st.pyplot(plot_heatmap(ideal, f"Ideal Margins - {selected_supplier} | Group {group}"))
                    st.pyplot(plot_heatmap(difference, f"Difference Margins - {selected_supplier} | Group {group}"))

                st.subheader("📄 Export PDF Report for Supplier")
                if st.button("Generate PDF"):
                    pdf_buffer = io.BytesIO()
                    with PdfPages(pdf_buffer) as pdf:
                        pdf.savefig(plot_heatmap(actual_all, f"SUMMARY: Actual Margins - {selected_supplier}"))
                        pdf.savefig(plot_heatmap(ideal_all, f"SUMMARY: Ideal Margins - {selected_supplier}"))
                        pdf.savefig(plot_heatmap(diff_all, f"SUMMARY: Difference Margins - {selected_supplier}"))

                        for group in group_options:
                            sub = data[data['Sales Discount Group'] == group]
                            actual = sub.pivot_table(values='Margin %', index='Customer Type', columns='Customer Size', aggfunc='mean')
                            actual = actual.reindex(index=CUSTOMER_TYPES, columns=CUSTOMER_SIZES)
                            ideal = get_ideal_margin_matrix()
                            difference = actual - ideal

                            pdf.savefig(plot_heatmap(actual, f"Actual Margins - {selected_supplier} | Group {group}"))
                            pdf.savefig(plot_heatmap(ideal, f"Ideal Margins - {selected_supplier} | Group {group}"))
                            pdf.savefig(plot_heatmap(difference, f"Difference Margins - {selected_supplier} | Group {group}"))

                    st.download_button(
                        label="📥 Download Supplier Report PDF",
                        data=pdf_buffer.getvalue(),
                        file_name=f"{selected_supplier.replace(' ', '_')}_report.pdf",
                        mime="application/pdf"
                    )
            else:
                st.info("📄 PDF generation and group-level heatmaps are only available when a specific supplier is selected.")

    except Exception as e:
        st.error(f"Error fetching or processing data: {e}")
