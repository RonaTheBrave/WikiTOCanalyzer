import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import requests

def get_revision_content(title, revid=None):
    """
    Fetch content of a specific revision or current version of a Wikipedia page
    """
    api_url = "https://en.wikipedia.org/w/api.php"
    
    if revid:
        params = {
            "action": "parse",
            "oldid": revid,
            "format": "json",
            "prop": "wikitext",
            "formatversion": "2"
        }
    else:
        params = {
            "action": "parse",
            "page": title,
            "format": "json",
            "prop": "wikitext",
            "formatversion": "2"
        }
    
    try:
        response = requests.get(api_url, params=params)
        data = response.json()
        
        if 'parse' in data and 'wikitext' in data['parse']:
            return data['parse']['wikitext']
        return None
            
    except Exception as e:
        st.error(f"Error in API request: {str(e)}")
        return None

def get_page_history(title):
    """
    Fetch list of revisions for a Wikipedia page
    """
    api_url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "prop": "revisions",
        "titles": title,
        "rvprop": "ids|timestamp",
        "rvlimit": "500",
        "formatversion": "2",
        "continue": "",
        "rvdir": "older"
    }
    
    st.write("Fetching revision history...")
    
    all_revisions = []
    continue_data = {}
    
    while True:
        request_params = {**params, **continue_data}
        
        try:
            response = requests.get(api_url, params=request_params)
            data = response.json()
            
            if 'query' in data and 'pages' in data['query']:
                page = data['query']['pages'][0]
                if 'revisions' in page:
                    all_revisions.extend(page['revisions'])
            
            if 'continue' in data:
                continue_data = data['continue']
            else:
                break
                
        except Exception as e:
            st.error(f"Error fetching revisions: {str(e)}")
            break
    
    return all_revisions

def extract_toc(wikitext):
    """
    Extract table of contents from Wikipedia page content.
    """
    sections = []
    try:
        lines = wikitext.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('==') and line.endswith('=='):
                title = line.strip('=').strip()
                level = (len(line) - len(title)) // 2
                if title and level > 0:
                    sections.append({
                        "title": title,
                        "level": level
                    })
    except Exception as e:
        st.error(f"Error extracting sections: {str(e)}")
    return sections

def process_revision_history(title):
    """
    Process revision history and extract TOC for each year
    """
    revisions = get_page_history(title)
    
    yearly_revisions = {}
    years_processed = set()
    
    for rev in reversed(revisions):
        year = datetime.strptime(rev['timestamp'], "%Y-%m-%dT%H:%M:%SZ").year
        
        if year not in years_processed and year >= 2019:
            yearly_revisions[year] = rev['revid']
            years_processed.add(year)
    
    toc_history = {}
    for year, revid in sorted(yearly_revisions.items()):
        content = get_revision_content(title, revid)
        if content:
            sections = extract_toc(content)
            if sections:
                toc_history[str(year)] = sections
    
    return toc_history

# Set up Streamlit page
st.set_page_config(page_title="Wikipedia TOC History Viewer", layout="wide")

st.title("Wikipedia Table of Contents History Viewer")
st.write("This tool shows how the table of contents structure has evolved over time")

# Input section
with st.sidebar:
    st.header("Settings")
    wiki_page = st.text_input(
        "Enter Wikipedia Page Title",
        "Dog",
        help="Enter the exact title as it appears in the Wikipedia URL"
    )

if wiki_page:
    try:
        with st.spinner("Analyzing page history..."):
            # Get current TOC first
            current_content = get_revision_content(wiki_page)
            if current_content:
                st.success("Successfully retrieved current version")
                current_sections = extract_toc(current_content)
                
                # Get historical versions
                toc_history = process_revision_history(wiki_page)
                
                if toc_history:
                    st.success(f"Found historical versions from {len(toc_history)} different years")
                    
                    # Create tabs for different views
                    tab1, tab2 = st.tabs(["Timeline View", "Edit Activity"])
                    
                    with tab1:
                        # Controls
                        controls_col1, controls_col2, controls_col3, _ = st.columns([1, 1, 1, 4])
                        with controls_col1:
                            zoom_level = st.slider("Zoom", 50, 200, 100, 10, 
                                                 label_visibility="collapsed",
                                                 key="unique_zoom_slider")
                        with controls_col2:
                            st.button("Fit Screen", key="unique_fit_btn")
                        with controls_col3:
                        with controls_col3:
                            # Create proper CSV data
                            csv_data = []
                            for year, sections in sorted(toc_history.items()):
                                for section in sections:
                                    csv_data.append({
                                        'Year': year,
                                        'Section': section['title'],
                                        'Level': section['level']
                                    })
                            csv_df = pd.DataFrame(csv_data)
                            st.download_button(
                                "Download CSV",
                                data=csv_df.to_csv(index=False),
                                file_name="toc_history.csv",
                                mime="text/csv",
                                key="unique_download_btn"
                            )
                        
                        # Timeline view styling
                        st.markdown("""
                            <style>
                                .stHorizontalBlock {
                                    overflow-x: auto;
                                    padding: 1rem;
                                    background: white;
                                    border: 1px solid #e5e7eb;
                                    border-radius: 4px;
                                }
                                .section-title {
                                    padding: 2px 4px;
                                    margin: 2px 0;
                                    white-space: nowrap;
                                    overflow: hidden;
                                    text-overflow: ellipsis;
                                }
                                .section-new {
                                    background-color: #dcfce7;
                                }
                            </style>
                        """, unsafe_allow_html=True)
                        
                        # Create columns for each year
                        cols = st.columns(len(toc_history))
                        
                        # Display content in columns
                        for idx, (year, sections) in enumerate(sorted(toc_history.items())):
                            with cols[idx]:
                                st.markdown(f"### {year}")
                                st.markdown("---")
                                for section in sections:
                                    indent = "&nbsp;" * (4 * (section['level'] - 1))
                                    st.markdown(
                                        f"{indent}{section['title']}",
                                        unsafe_allow_html=True
                                    )
                    
                    with tab2:
                        # Edit Activity view code here...
                        pass
                else:
                    st.warning("No historical versions found.")
            else:
                st.error("Could not retrieve page content.")

    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.info("Please check if the Wikipedia page title is correct and try again.")
