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
        # Get specific revision
        params = {
            "action": "parse",
            "oldid": revid,
            "format": "json",
            "prop": "wikitext",
            "formatversion": "2"
        }
    else:
        # Get current version
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
        "rvlimit": "500",  # Get maximum allowed revisions
        "formatversion": "2"
    }
    
    st.write("Fetching revision history...")
    st.write("Parameters:", params)
    
    try:
        response = requests.get(api_url, params=params)
        data = response.json()
        
        st.write("Response Status:", response.status_code)
        
        if 'query' in data and 'pages' in data['query']:
            page = data['query']['pages'][0]
            if 'revisions' in page:
                revisions = page['revisions']
                st.write(f"Found {len(revisions)} revisions")
                return revisions
        
        st.write("Full Response:", data)
        return []
            
    except Exception as e:
        st.error(f"Error fetching history: {str(e)}")
        return []

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
    
    # Group revisions by year
    yearly_revisions = {}
    for rev in revisions:
        year = datetime.strptime(rev['timestamp'], "%Y-%m-%dT%H:%M:%SZ").year
        if year not in yearly_revisions:
            yearly_revisions[year] = rev['revid']
    
    # Get TOC for each year's first revision
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
        help="Enter the exact title as it appears in the Wikipedia URL (e.g., 'Python_(programming_language)')"
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
                        # Display TOC timeline
                        for year, sections in sorted(toc_history.items()):
                            col = st.columns([1, 3])
                            with col[0]:
                                st.write(f"**{year}**")
                            with col[1]:
                                for section in sections:
                                    indent = "&nbsp;" * (4 * (section['level'] - 1))
                                    st.markdown(
                                        f"{indent}{section['title']} "
                                        f"<span style='color:gray'>{'*' * section['level']}</span>",
                                        unsafe_allow_html=True
                                    )
                                st.markdown("---")
                    
                    with tab2:
                        # Create heatmap data
                        edit_data = []
                        for year, sections in toc_history.items():
                            for section in sections:
                                edit_data.append({
                                    'Year': int(year),
                                    'Section': section['title'],
                                    'Level': section['level']
                                })
                        
                        if edit_data:
                            df = pd.DataFrame(edit_data)
                            fig = px.density_heatmap(
                                df,
                                x='Year',
                                y='Section',
                                title='Section Activity Over Time',
                                color_continuous_scale='Reds'
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.warning("No data available for visualization.")
                else:
                    st.warning("No historical versions found.")
            else:
                st.error("Could not retrieve page content.")

    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.info("Please check if the Wikipedia page title is correct and try again.")
