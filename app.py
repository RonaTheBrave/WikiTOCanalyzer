import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import requests
from typing import Dict, List, Optional
import numpy as np

# Configuration and styling
st.set_page_config(
    page_title="Wikipedia TOC History Viewer",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS to match React styling
st.markdown("""
<style>
    /* Card-like containers */
    .stApp {
        background-color: #f9fafb;
    }
    .element-container {
        background-color: white;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    
    /* Controls styling */
    .stRadio > label {
        background-color: transparent !important;
        border: none !important;
    }
    .stRadio > div {
        flex-direction: row !important;
        gap: 0.5rem !important;
    }
    
    /* Timeline view styling */
    .timeline-container {
        display: flex;
        overflow-x: auto;
        gap: 1rem;
        padding: 1rem;
        background: white;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    /* Section styling */
    .section-title {
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        margin: 0.25rem 0;
        font-size: 0.875rem;
    }
    .section-new {
        background-color: #dcfce7;
    }
    .section-renamed {
        background-color: #fef3c7;
    }
    .section-removed {
        background-color: #fee2e2;
    }
    
    /* Heatmap styling */
    .heatmap-cell {
        text-align: center;
        padding: 0.25rem;
        border-radius: 4px;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Custom button styling */
    .stButton > button {
        border-radius: 4px;
        padding: 0.375rem 0.75rem;
        font-size: 0.875rem;
        border: 1px solid #e5e7eb;
        background-color: white;
    }
    .stButton > button:hover {
        border-color: #d1d5db;
        background-color: #f9fafb;
    }
</style>
""", unsafe_allow_html=True)

def create_edit_activity_heatmap(toc_history: Dict) -> go.Figure:
    """
    Create a heatmap visualization of edit activity
    """
    # Process data to get edit counts per section per year
    sections = []
    years = sorted(toc_history.keys())
    
    for year, data in toc_history.items():
        for section in data["sections"]:
            section_name = section["title"]
            if section_name not in sections:
                sections.append(section_name)
    
    # Create matrix for heatmap
    edit_matrix = []
    for section in sections:
        row = []
        for year in years:
            # Count section presence and changes
            year_data = toc_history[year]
            count = 0
            for s in year_data["sections"]:
                if s["title"] == section:
                    count = 1
                    if s.get("isNew") or s.get("isRenamed"):
                        count = 2
            row.append(count)
        edit_matrix.append(row)
    
    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=edit_matrix,
        x=years,
        y=sections,
        colorscale=[
            [0, '#ffffff'],
            [0.5, '#ffcccc'],
            [1, '#ff0000']
        ],
        showscale=False
    ))
    
    fig.update_layout(
        title="Section Edit Activity",
        xaxis_title="Year",
        yaxis_title="Section",
        height=max(400, len(sections) * 30)
    )
    
    return fig

def main():
    # Title and description
    st.title("Wikipedia TOC History Viewer")
    
    # Page settings in sidebar
    with st.sidebar:
        st.header("Settings")
        wiki_page = st.text_input(
            "Wikipedia Page Title",
            "Opioid-induced hyperalgesia",
            help="Enter the exact title as it appears in the Wikipedia URL"
        )
        show_renames = st.toggle(
            "Enable Rename Detection",
            True,
            help="Detect and highlight renamed sections"
        )
    
    # Main content area
    if wiki_page:
        # View mode selection
        view_mode = st.radio(
            "View Mode",
            ["Timeline View", "Edit Activity", "Section Count"],
            horizontal=True,
            key="view_mode"
        )
        
        # Controls row
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
        with col1:
            if view_mode == "Timeline View":
                zoom_level = st.slider(
                    "Zoom",
                    min_value=50,
                    max_value=200,
                    value=100,
                    step=10,
                    format="%d%%"
                )
        
        with col2:
            if view_mode == "Timeline View":
                st.button("⟲ Reset Zoom")
        
        with col3:
            if view_mode == "Timeline View":
                st.download_button(
                    "↓ Download Data",
                    data="", # TODO: Implement CSV export
                    file_name="toc_history.csv",
                    mime="text/csv"
                )
        
        # Legend for Timeline View
        if view_mode == "Timeline View":
            st.markdown("""
                <div style="display: flex; gap: 1rem; margin-bottom: 1rem; font-size: 0.875rem;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <div style="width: 12px; height: 12px; background-color: #dcfce7; border-radius: 3px;"></div>
                        <span>New sections</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <div style="width: 12px; height: 12px; background-color: #fef3c7; border-radius: 3px;"></div>
                        <span>Renamed sections</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <div style="width: 12px; height: 12px; background-color: #fee2e2; border-radius: 3px;"></div>
                        <span>Sections to be removed</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        
        # Main content based on view mode
        if view_mode == "Timeline View":
            # TODO: Implement timeline view with proper styling and zoom
            pass
        
        elif view_mode == "Edit Activity":
            # Sample data for demonstration
            toc_history = {
                "2019": {"sections": [{"title": "Introduction", "isNew": True}]},
                "2020": {"sections": [{"title": "Introduction"}, {"title": "Methods", "isNew": True}]},
                "2021": {"sections": [{"title": "Introduction"}, {"title": "Methods", "isRenamed": True}]}
            }
            
            fig = create_edit_activity_heatmap(toc_history)
            st.plotly_chart(fig, use_container_width=True)
        
        elif view_mode == "Section Count":
            # TODO: Implement section count visualization
            pass

if __name__ == "__main__":
    main()
