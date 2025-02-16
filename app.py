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
    
    /* Timeline column styling */
    .timeline-column {
        background-color: white;
        border: 1px solid #e5e7eb;
        border-radius: 4px;
        padding: 1rem;
        margin: 0.5rem;
        min-width: 250px;
    }
    
    .year-header {
        font-weight: 600;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #e5e7eb;
        margin-bottom: 0.5rem;
    }
    
    /* Section styling */
    .section-title {
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        margin: 0.25rem 0;
        font-size: 0.875rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .section-level-1 { margin-left: 0px; }
    .section-level-2 { margin-left: 20px; }
    .section-level-3 { margin-left: 40px; }
    
    .section-new {
        background-color: #dcfce7;
    }
    .section-renamed {
        background-color: #fef3c7;
    }
    .section-removed {
        background-color: #fee2e2;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Container for horizontal scrolling */
    .timeline-container {
        display: flex;
        overflow-x: auto;
        padding: 1rem;
        gap: 1rem;
        background: white;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

def get_sample_data():
    """Return sample TOC history data for testing"""
    return {
        "2019": {
            "sections": [
                {"title": "Signs and symptoms", "level": 1},
                {"title": "Pathophysiology", "level": 1},
                {"title": "Diagnosis", "level": 1},
                {"title": "Prevention", "level": 1, "isNew": True},
                {"title": "Treatment", "level": 1},
                {"title": "References", "level": 1}
            ]
        },
        "2020": {
            "sections": [
                {"title": "Signs and symptoms", "level": 1},
                {"title": "Pathophysiology", "level": 1},
                {"title": "Mechanism", "level": 2, "isNew": True},
                {"title": "Diagnosis", "level": 1},
                {"title": "Prevention", "level": 1},
                {"title": "Treatment", "level": 1},
                {"title": "References", "level": 1}
            ]
        },
        "2021": {
            "sections": [
                {"title": "Signs and symptoms", "level": 1},
                {"title": "Pathophysiology", "level": 1},
                {"title": "Mechanism", "level": 2},
                {"title": "Diagnosis", "level": 1},
                {"title": "Prevention", "level": 1},
                {"title": "Treatment", "level": 1},
                {"title": "Management strategies", "level": 2, "isNew": True},
                {"title": "References", "level": 1}
            ]
        }
    }

def render_timeline_column(year: str, sections: List[Dict], zoom_level: int):
    """Render a single year column in the timeline"""
    column_html = f'<div class="timeline-column" style="transform: scale({zoom_level/100});">'
    column_html += f'<div class="year-header">{year}</div>'
    
    for section in sections:
        # Determine section classes
        classes = [f"section-title section-level-{section['level']}"]
        if section.get("isNew"):
            classes.append("section-new")
        if section.get("isRenamed"):
            classes.append("section-renamed")
        if section.get("isRemoved"):
            classes.append("section-removed")
        
        # Add section to column
        column_html += f'<div class="{" ".join(classes)}">{section["title"]}</div>'
    
    column_html += '</div>'
    return column_html

def render_timeline(toc_history: Dict, zoom_level: int):
    """Render the complete timeline view"""
    timeline_html = '<div class="timeline-container">'
    
    for year, data in sorted(toc_history.items()):
        timeline_html += render_timeline_column(year, data["sections"], zoom_level)
    
    timeline_html += '</div>'
    return timeline_html

def create_section_count_chart(toc_history: Dict) -> go.Figure:
    """Create section count visualization"""
    counts = []
    for year, data in sorted(toc_history.items()):
        total = len(data["sections"])
        new = len([s for s in data["sections"] if s.get("isNew", False)])
        counts.append({
            "Year": year,
            "Total Sections": total,
            "New Sections": new
        })
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[c["Year"] for c in counts],
        y=[c["Total Sections"] for c in counts],
        name="Total Sections",
        marker_color='rgb(55, 83, 109)'
    ))
    fig.add_trace(go.Bar(
        x=[c["Year"] for c in counts],
        y=[c["New Sections"] for c in counts],
        name="New Sections",
        marker_color='rgb(26, 118, 255)'
    ))
    
    fig.update_layout(
        title="Section Count Evolution",
        xaxis_title="Year",
        yaxis_title="Number of Sections",
        barmode='group',
        bargap=0.15,
        bargroupgap=0.1
    )
    
    return fig

def main():
    st.title("Wikipedia TOC History Viewer")
    
    # Sidebar settings
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
    
    if wiki_page:
        # View mode selection
        view_mode = st.radio(
            "View Mode",
            ["Timeline View", "Edit Activity", "Section Count"],
            horizontal=True,
            key="view_mode"
        )
        
        # Get sample data (replace with actual API calls later)
        toc_history = get_sample_data()
        
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
                        <span>Removed sections</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        
        # Main content based on view mode
        if view_mode == "Timeline View":
            timeline_html = render_timeline(toc_history, zoom_level)
            st.markdown(timeline_html, unsafe_allow_html=True)
        
        elif view_mode == "Section Count":
            fig = create_section_count_chart(toc_history)
            st.plotly_chart(fig, use_container_width=True)
        
        elif view_mode == "Edit Activity":
            st.info("Edit Activity view is coming soon!")

if __name__ == "__main__":
    main()
