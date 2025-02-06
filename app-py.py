import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
from utils.wiki_utils import get_page_history, get_toc_history

st.set_page_config(page_title="Wikipedia TOC History Viewer", layout="wide")

st.title("Wikipedia TOC History Viewer")

# Input section
with st.sidebar:
    st.header("Settings")
    wiki_page = st.text_input(
        "Enter Wikipedia Page Title",
        "Opioid-induced hyperalgesia",
        help="Enter the exact title as it appears in the Wikipedia URL"
    )
    
    end_date = st.date_input(
        "End Date",
        datetime.now().date(),
        help="Select the end date for the history view"
    )
    
    years_back = st.slider(
        "Years of History",
        min_value=1,
        max_value=10,
        value=5,
        help="Select how many years of history to view"
    )
    
    start_date = end_date - timedelta(days=365*years_back)

if wiki_page:
    try:
        with st.spinner("Fetching page history..."):
            # Get TOC history
            toc_history = get_toc_history(wiki_page, start_date, end_date)
            
            # Display TOC history
            st.header("Table of Contents History")
            
            # Create tabs for different views
            tab1, tab2 = st.tabs(["Timeline View", "Edit Activity"])
            
            with tab1:
                # Display TOC timeline
                for date, sections in toc_history.items():
                    col = st.columns([1, 3])
                    with col[0]:
                        st.write(f"**{date}**")
                    with col[1]:
                        for section in sections:
                            indent = "&nbsp;" * (4 * (section['level'] - 1))
                            status = "🆕 " if section.get('isNew') else ""
                            st.markdown(
                                f"{indent}{status}{section['title']} "
                                f"<span style='color:gray'>{'*' * section['level']}</span>",
                                unsafe_allow_html=True
                            )
                        st.markdown("---")
            
            with tab2:
                # Convert data for heatmap
                edit_data = []
                for date, sections in toc_history.items():
                    year = datetime.strptime(date, "%Y").year
                    for section in sections:
                        edit_data.append({
                            'Year': year,
                            'Section': section['title'],
                            'Level': section['level'],
                            'Status': 'New' if section.get('isNew') else 'Existing'
                        })
                
                df = pd.DataFrame(edit_data)
                
                # Create heatmap using plotly
                fig = px.density_heatmap(
                    df,
                    x='Year',
                    y='Section',
                    title='Section Edit Activity',
                    color_continuous_scale='Reds'
                )
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.info("Please check if the Wikipedia page title is correct and try again.")