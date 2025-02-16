import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import requests
from typing import Dict, List, Optional, Any
from difflib import SequenceMatcher

# Configuration
st.set_page_config(
    page_title="Wikipedia TOC History Viewer",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS matching the React version exactly
st.markdown("""
<style>
    .stApp {
        background-color: #f9fafb;
    }
    
    .timeline-container {
        display: flex;
        overflow-x: auto;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 4px;
        margin: 1rem 0;
    }
    
    .year-column {
        flex: 0 0 208px;
        padding: 0.5rem;
        border-right: 1px solid #e5e7eb;
        overflow: hidden;
    }
    
    .year-column:last-child {
        border-right: none;
    }
    
    .year-header {
        padding: 0.25rem;
        margin-bottom: 0.25rem;
        border-bottom: 1px solid #e5e7eb;
        font-size: 0.875rem;
        font-weight: 500;
        text-align: left;
        position: sticky;
        top: 0;
        background: white;
        z-index: 1;
    }
    
    .section-item {
        position: relative;
        display: flex;
        align-items: center;
        padding: 0.125rem 0;
    }
    
    .section-content {
        display: flex;
        align-items: center;
        gap: 0.25rem;
        padding: 0.125rem 0.25rem;
        border-radius: 0.25rem;
        font-size: 0.875rem;
        line-height: 1.25rem;
    }
    
    .section-new {
        background-color: #dcfce7;
    }
    
    .section-renamed {
        background-color: #fef3c7;
    }
    
    .section-level {
        color: #6b7280;
        font-family: ui-monospace, monospace;
        font-size: 0.75rem;
        margin-left: 0.25rem;
    }
    
    .section-children {
        margin-left: 0.75rem;
        padding-left: 0.75rem;
        border-left: 1px solid #e5e7eb;
    }
    
    /* Hide Streamlit components */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    
    /* Legend styling */
    .legend {
        display: flex;
        gap: 1rem;
        margin-bottom: 1rem;
        padding: 0.5rem;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 4px;
        font-size: 0.875rem;
    }
    
    .legend-item {
        display: flex;
        align-items: center;
        gap: 0.25rem;
    }
    
    .legend-color {
        width: 0.75rem;
        height: 0.75rem;
        border-radius: 0.25rem;
    }
</style>
""", unsafe_allow_html=True)

def build_section_tree(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build a hierarchical tree from flat sections list"""
    result = []
    stack = []
    
    for section in sections:
        level = section["level"]
        
        # Pop stack until we find parent or reach root
        while stack and stack[-1]["level"] >= level:
            stack.pop()
        
        new_node = {
            "title": section["title"],
            "level": level,
            "children": [],
            "isNew": section.get("isNew", False),
            "isRenamed": section.get("isRenamed", False),
            "previousTitle": section.get("previousTitle", None)
        }
        
        if not stack:  # Root level
            result.append(new_node)
        else:  # Add to parent's children
            stack[-1]["children"].append(new_node)
        
        stack.append(new_node)
    
    return result

def render_section(section: Dict[str, Any], depth: int = 0) -> str:
    """Render a single section with its children"""
    indent = "margin-left: {}rem;".format(depth * 0.75)
    classes = ["section-content"]
    if section.get("isNew"):
        classes.append("section-new")
    if section.get("isRenamed"):
        classes.append("section-renamed")
    
    html = f'''
    <div class="section-item" style="{indent}">
        <div class="{' '.join(classes)}">
            <span>{section["title"]}</span>
            <span class="section-level">{"*" * section["level"]}</span>
            {f'<span style="font-size: 0.75rem; color: #666;">(was: {section["previousTitle"]})</span>' if section.get("isRenamed") else ""}
        </div>
    </div>
    '''
    
    if section["children"]:
        html += '<div class="section-children">'
        for child in section["children"]:
            html += render_section(child, depth + 1)
        html += '</div>'
    
    return html

def render_year_column(year: str, sections: List[Dict[str, Any]], revid: Optional[str] = None) -> str:
    """Render a complete year column"""
    year_link = f'<a href="https://en.wikipedia.org/w/index.php?oldid={revid}" target="_blank">{year}</a>' if revid else year
    
    html = f'''
    <div class="year-column">
        <div class="year-header">{year_link}</div>
        <div class="sections-container">
    '''
    
    tree = build_section_tree(sections)
    for section in tree:
        html += render_section(section)
    
    html += '</div></div>'
    return html

def render_timeline(toc_history: Dict[str, Any]) -> str:
    """Render the complete timeline view"""
    html = '<div class="timeline-container">'
    
    for year, data in sorted(toc_history.items()):
        html += render_year_column(year, data["sections"], data.get("revid"))
    
    html += '</div>'
    return html

# Rest of the code (get_page_history, extract_toc, etc.) remains the same...

def main():
    st.title("Wikipedia TOC History Viewer")
    
    # Sidebar settings
    with st.sidebar:
        st.header("Settings")
        wiki_page = st.text_input(
            "Wikipedia Page Title",
            "Opioid-induced hyperalgesia"
        )
        
        current_year = datetime.now().year
        col1, col2 = st.columns(2)
        with col1:
            start_year = st.number_input(
                "Start Year",
                min_value=2001,
                max_value=current_year-1,
                value=2019
            )
        with col2:
            end_year = st.number_input(
                "End Year",
                min_value=start_year+1,
                max_value=current_year,
                value=min(start_year+5, current_year)
            )
        
        show_renames = st.toggle(
            "Enable Rename Detection",
            True,
            help="Detect and highlight renamed sections"
        )
    
    if wiki_page:
        # Add legend
        st.markdown("""
        <div class="legend">
            <div class="legend-item">
                <div class="legend-color" style="background-color: #dcfce7;"></div>
                <span>New sections</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #fef3c7;"></div>
                <span>Renamed sections</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        try:
            with st.spinner("Analyzing page history..."):
                # Your existing data fetching code...
                # For testing, let's use sample data
                sample_data = {
                    "2019": {
                        "sections": [
                            {"title": "Signs and symptoms", "level": 1},
                            {"title": "Pathophysiology", "level": 1, "children": [
                                {"title": "Mechanism", "level": 2}
                            ]},
                            {"title": "Treatment", "level": 1}
                        ]
                    },
                    "2020": {
                        "sections": [
                            {"title": "Signs and symptoms", "level": 1},
                            {"title": "Pathophysiology", "level": 1, "children": [
                                {"title": "Mechanism", "level": 2},
                                {"title": "Risk factors", "level": 2, "isNew": True}
                            ]},
                            {"title": "Treatment", "level": 1}
                        ]
                    }
                }
                
                st.markdown(render_timeline(sample_data), unsafe_allow_html=True)
                
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.info("Please check if the Wikipedia page title is correct and try again.")

if __name__ == "__main__":
    main()
