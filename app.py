
import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import io

# Constants
CUSTOMER_TYPES = ['IND_OEM', 'MOB_OEM', 'JOBBER', 'USER', 'TP']
CUSTOMER_SIZES = ['HUGE', 'LARGE', 'MED', 'SMALL', 'TINY']
MINIMUM_MARGINS = {'IND_OEM': 35, 'MOB_OEM': 28, 'JOBBER': 40, 'USER': 35, 'TP': 42}
SIZE_OFFSETS = {'HUGE': 0, 'LARGE': 2, 'MED': 4, 'SMALL': 6, 'TINY': 8}

@st.cache_data
def load_data(file):
    df = pd.read_excel(file)
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

st.title("📊 Supplier and Discount Group Margin Analyzer")

file = st.file_uploader("Upload Excel File", type=['xlsx'])

if file:
    df = load_data(file)
    all_suppliers = sorted(df['Supplier Name'].unique())
    suppliers = ['ALL'] + all_suppliers
    selected_supplier = st.selectbox("Select Supplier", suppliers)

    exclude_misc = st.checkbox("Exclude Sales Discount Groups starting or ending with 'Z' (Miscellaneous)", value=True)

    # Apply filters
    data = df.copy()
    if exclude_misc:
        data = data[~data['Sales Discount Group'].str.startswith('Z')]
        data = data[~data['Sales Discount Group'].str.endswith('Z')]

    if selected_supplier != 'ALL':
        data = data[data['Supplier Name'] == selected_supplier]

    if data.empty:
        st.warning("No data available after filtering.")
    else:
        # Supplier or ALL level summary
        st.subheader(f"📊 {'Global' if selected_supplier == 'ALL' else 'Supplier'}-Level Summary Heatmaps")
        actual_all = data.pivot_table(values='Margin %', index='Customer Type', columns='Customer Size', aggfunc='mean')
        actual_all = actual_all.reindex(index=CUSTOMER_TYPES, columns=CUSTOMER_SIZES)
        ideal_all = get_ideal_margin_matrix()
        diff_all = actual_all - ideal_all

        st.pyplot(plot_heatmap(actual_all, f"SUMMARY: Actual Margins - {selected_supplier}"))
        st.pyplot(plot_heatmap(ideal_all, f"SUMMARY: Ideal Margins - {selected_supplier}"))
        st.pyplot(plot_heatmap(diff_all, f"SUMMARY: Difference Margins - {selected_supplier}"))

        if selected_supplier != 'ALL':
            # Display group-level heatmaps only if supplier is selected
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

            # PDF report export
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
                    file_name=f"{selected_supplier.replace(' ', '_')}_full_report.pdf",
                    mime="application/pdf"
                )
        else:
            st.info("📄 PDF generation and group-level views are only available when a specific supplier is selected.")
