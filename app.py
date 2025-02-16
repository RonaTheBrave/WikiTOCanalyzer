import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import requests
from typing import Dict, List, Optional
from difflib import SequenceMatcher

# Configuration
st.set_page_config(
    page_title="Wikipedia TOC History Viewer",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for proper side-by-side layout
st.markdown("""
<style>
    .stApp {
        background-color: #f9fafb;
    }
    
    .flex-container {
        display: flex;
        flex-direction: row;
        overflow-x: auto;
        gap: 0;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 4px;
        margin: 1rem 0;
    }
    
    .year-column {
        flex: 0 0 300px;
        border-right: 1px solid #e5e7eb;
        overflow: hidden;
    }
    
    .year-column:last-child {
        border-right: none;
    }
    
    .year-header {
        padding: 1rem;
        font-weight: 600;
        border-bottom: 1px solid #e5e7eb;
        text-align: center;
        background: white;
        position: sticky;
        top: 0;
    }
    
    .sections-list {
        padding: 1rem;
    }
    
    .section {
        padding: 0.25rem 0.5rem;
        margin: 0.25rem 0;
        border-radius: 4px;
        font-size: 0.875rem;
    }
    
    .section.new {
        background-color: #dcfce7;
    }
    
    .section.renamed {
        background-color: #fef3c7;
    }
    
    .indent-1 { margin-left: 0; }
    .indent-2 { margin-left: 1.5rem; }
    .indent-3 { margin-left: 3rem; }
    
    /* Hide Streamlit components */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    
    /* Custom controls styling */
    .custom-controls {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 0.5rem;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 4px;
        margin-bottom: 1rem;
    }
    
    .stSlider {
        max-width: 200px;
    }
</style>
""", unsafe_allow_html=True)

def get_page_history(title: str, start_year: int, end_year: int) -> List[Dict]:
    """Fetch Wikipedia page revision history"""
    api_url = "https://en.wikipedia.org/w/api.php"
    start_timestamp = f"{start_year}-01-01T00:00:00Z"
    end_timestamp = f"{end_year}-12-31T23:59:59Z"
    
    params = {
        "action": "query",
        "format": "json",
        "prop": "revisions",
        "titles": title,
        "rvprop": "ids|timestamp|content",
        "rvstart": end_timestamp,
        "rvend": start_timestamp,
        "rvlimit": "500",
        "formatversion": "2"
    }
    
    revisions = []
    continue_data = {}
    
    while True:
        try:
            response = requests.get(api_url, params={**params, **continue_data})
            data = response.json()
            
            if 'query' in data and 'pages' in data['query']:
                page = data['query']['pages'][0]
                if 'revisions' in page:
                    revisions.extend(page['revisions'])
            
            if 'continue' in data:
                continue_data = data['continue']
            else:
                break
                
        except Exception as e:
            st.error(f"Error fetching revisions: {str(e)}")
            break
    
    return revisions

def extract_toc(wikitext: str) -> List[Dict]:
    """Extract TOC from wikitext"""
    sections = []
    current_level_stack = []
    
    for line in wikitext.split('\n'):
        if line.strip().startswith('==') and line.strip().endswith('=='):
            title = line.strip('=').strip()
            level = (len(line) - len(line.strip('='))) // 2
            
            sections.append({
                "title": title,
                "level": level
            })
    
    return sections

def render_year_column(year: str, sections: List[Dict], revid: Optional[str] = None) -> str:
    """Render a single year column"""
    year_link = f'<a href="https://en.wikipedia.org/w/index.php?oldid={revid}" target="_blank">{year}</a>' if revid else year
    
    html = f'''
    <div class="year-column">
        <div class="year-header">{year_link}</div>
        <div class="sections-list">
    '''
    
    for section in sections:
        classes = [
            "section",
            f"indent-{section['level']}",
            "new" if section.get('isNew') else "",
            "renamed" if section.get('isRenamed') else ""
        ]
        class_str = ' '.join(filter(None, classes))
        
        html += f'<div class="{class_str}">{section["title"]}</div>'
    
    html += '</div></div>'
    return html

def render_timeline(toc_history: Dict) -> str:
    """Render the complete timeline view"""
    html = '<div class="flex-container">'
    
    for year, data in sorted(toc_history.items()):
        html += render_year_column(year, data['sections'], data.get('revid'))
    
    html += '</div>'
    return html

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
    
    if wiki_page:
        # View mode selection
        view_mode = st.radio(
            "View Mode",
            ["Timeline View", "Section Count"],
            horizontal=True
        )
        
        try:
            with st.spinner("Analyzing page history..."):
                revisions = get_page_history(wiki_page, start_year, end_year)
                toc_history = {}
                
                # Process revisions
                for rev in revisions:
                    year = datetime.strptime(rev['timestamp'], "%Y-%m-%dT%H:%M:%SZ").year
                    if year not in toc_history and start_year <= year <= end_year:
                        try:
                            response = requests.get(
                                "https://en.wikipedia.org/w/api.php",
                                params={
                                    "action": "parse",
                                    "oldid": rev['revid'],
                                    "format": "json",
                                    "prop": "wikitext",
                                    "formatversion": "2"
                                }
                            )
                            data = response.json()
                            if 'parse' in data and 'wikitext' in data['parse']:
                                sections = extract_toc(data['parse']['wikitext'])
                                toc_history[str(year)] = {
                                    'sections': sections,
                                    'revid': rev['revid']
                                }
                        except Exception as e:
                            st.error(f"Error processing revision: {str(e)}")
                
                if toc_history:
                    if view_mode == "Timeline View":
                        st.markdown(render_timeline(toc_history), unsafe_allow_html=True)
                    else:
                        # Implement Section Count view here
                        st.info("Section Count view coming soon!")
                else:
                    st.warning("No historical versions found in the selected year range.")
                    
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.info("Please check if the Wikipedia page title is correct and try again.")

if __name__ == "__main__":
    main()
