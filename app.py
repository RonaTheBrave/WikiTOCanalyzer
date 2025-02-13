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
        "rvlimit": "500",
        "formatversion": "2",
        "continue": "",
        "rvdir": "older"  # Get older revisions first
    }
    
    st.write("Fetching revision history...")
    
    all_revisions = []
    continue_data = {}
    
    while True:
        # Add continue data if it exists
        request_params = {**params, **continue_data}
        st.write("Making API request with parameters:", request_params)
        
        try:
            response = requests.get(api_url, params=request_params)
            data = response.json()
            
            if 'query' in data and 'pages' in data['query']:
                page = data['query']['pages'][0]
                if 'revisions' in page:
                    all_revisions.extend(page['revisions'])
                    st.write(f"Retrieved {len(page['revisions'])} revisions (Total: {len(all_revisions)})")
            
            # Check if there are more revisions to fetch
            if 'continue' in data:
                continue_data = data['continue']
                st.write("More revisions available, continuing...")
            else:
                break
                
        except Exception as e:
            st.error(f"Error fetching revisions: {str(e)}")
            break
    
    st.write(f"Total revisions retrieved: {len(all_revisions)}")
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
    
    # Group revisions by year
    yearly_revisions = {}
    years_processed = set()
    current_year = datetime.now().year
    
    st.write("Processing revisions by year...")
    
    # Process revisions in chronological order
    for rev in reversed(revisions):
        year = datetime.strptime(rev['timestamp'], "%Y-%m-%dT%H:%M:%SZ").year
        
        # Only process years we haven't seen yet and stop at 2019
        if year not in years_processed and year >= 2019:
            yearly_revisions[year] = rev['revid']
            years_processed.add(year)
            st.write(f"Found revision for year {year}: {rev['revid']}")
    
    years_found = sorted(yearly_revisions.keys())
    st.write(f"Found revisions for years: {years_found}")
    
    # Get TOC for each year's revision
    toc_history = {}
    for year, revid in sorted(yearly_revisions.items()):
        st.write(f"Processing year {year} (revision {revid})")
        content = get_revision_content(title, revid)
        if content:
            st.write(f"Got content for year {year} ({len(content)} bytes)")
            sections = extract_toc(content)
            if sections:
                st.write(f"Found {len(sections)} sections for year {year}")
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
                        # Add zoom control
                        zoom_level = st.slider("Zoom", min_value=50, max_value=200, value=100, step=10, format="%d%%")
                        zoom_scale = zoom_level / 100.0
                        
                        # Create container for horizontal scrolling with zoom
                        st.markdown(f"""
                            <style>
                                .stHorizontalBlock {{
                                    overflow-x: auto;
                                    display: flex;
                                    background: white;
                                    border: 1px solid #e5e7eb;
                                    border-radius: 4px;
                                    padding: 0;
                                    margin: 1rem 0;
                                }}
                                [data-testid="column"] {{
                                    border-right: 1px solid #e5e7eb;
                                    padding: 1rem !important;
                                    min-width: 300px;
                                }}
                                .year-header {{
                                    font-weight: 600;
                                    padding-bottom: 0.5rem;
                                    margin-bottom: 0.5rem;
                                    border-bottom: 1px solid #e5e7eb;
                                    font-size: {14 * zoom_scale}px;
                                }}
                                .section-title {{
                                    padding: 2px 4px;
                                    margin: 2px 0;
                                    overflow: hidden;
                                    text-overflow: ellipsis;
                                    white-space: nowrap;
                                    position: relative;
                                    font-size: {13 * zoom_scale}px;
                                }}
                                .section-title:hover {{
                                    white-space: normal;
                                    background-color: #f3f4f6;
                                    z-index: 1000;
                                }}
                                .section-new {{
                                    background-color: #dcfce7;
                                }}
                                .section-deleted {{
                                    background-color: #fee2e2;
                                }}
                                .hierarchy-line {{
                                    border-left: 2px solid #e5e7eb;
                                    position: absolute;
                                    left: 0;
                                    top: 0;
                                    bottom: 0;
                                }}
                                .indented-1 {{ padding-left: 1.5rem; }}
                                .indented-2 {{ padding-left: 3rem; }}
                                .indented-3 {{ padding-left: 4.5rem; }}
                            </style>
                        """, unsafe_allow_html=True)
                        
                        # Create columns for all years
                        cols = st.columns(len(toc_history))
                        
                        # Fill each column with its year data
                        for idx, (year, sections) in enumerate(sorted(toc_history.items())):
                            with cols[idx]:
                                # Year header
                                st.markdown(f'<div class="year-header">{year}</div>', unsafe_allow_html=True)
                                
                                # Sections
                                for section in sections:
                                    # Determine section status
                                    status_class = "section-new" if section.get('isNew') else ""
                                    status_class = "section-deleted" if section.get('isDeleted') else status_class
                                    
                                    # Create indentation class based on level
                                    indent_class = f"indented-{section['level'] - 1}" if section['level'] > 1 else ""
                                    
                                    # Create hierarchy lines based on level
                                    hierarchy_lines = ""
                                    for i in range(1, section['level']):
                                        left_position = i * 1.5 - 1.25  # Adjust position of lines
                                        hierarchy_lines += f'<div class="hierarchy-line" style="left: {left_position}rem"></div>'
                                    
                                    st.markdown(
                                        f'<div class="section-title {status_class} {indent_class}" title="{section["title"]}">'
                                        f'{hierarchy_lines}{section["title"]}'
                                        f'</div>',
                                        unsafe_allow_html=True
                                    )
                        
                        # Create columns for all years
                        cols = st.columns(len(toc_history))
                        
                        # Fill each column with its year data
                        for idx, (year, sections) in enumerate(sorted(toc_history.items())):
                            with cols[idx]:
                                # Year header
                                st.markdown(f'<div class="year-header">{year}</div>', unsafe_allow_html=True)
                                
                                # Sections
                                for section in sections:
                                    # Determine section status
                                    status_class = "section-new" if section.get('isNew') else ""
                                    status_class = "section-deleted" if section.get('isDeleted') else status_class
                                    
                                    # Create indentation class based on level
                                    indent_class = f"indented-{section['level'] - 1}" if section['level'] > 1 else ""
                                    
                                    # Create minimal level indicator (just dots)
                                    level_indicator = "·" * section['level']
                                    
                                    st.markdown(
                                        f'<div class="section-title {status_class} {indent_class}">'
                                        f'{section["title"]} '
                                        f'<span class="level-indicator">{level_indicator}</span>'
                                        f'</div>',
                                        unsafe_allow_html=True
                                    )
                    
                    with tab2:
                        # Create heatmap data
                        st.write("### Section Activity Heatmap")
                        st.write("Shows when different sections appeared and their relative positions.")
                        
                        edit_data = []
                        all_sections = set()
                        for year, sections in toc_history.items():
                            for section in sections:
                                edit_data.append({
                                    'Year': int(year),
                                    'Section': section['title'],
                                    'Level': section['level']
                                })
                                all_sections.add(section['title'])
                        
                        if edit_data:
                            df = pd.DataFrame(edit_data)
                            
                            # Sort sections by their most common level
                            section_levels = df.groupby('Section')['Level'].mean().sort_values()
                            ordered_sections = section_levels.index.tolist()
                            
                            fig = px.density_heatmap(
                                df,
                                x='Year',
                                y='Section',
                                category_orders={'Section': ordered_sections},
                                title='Section Presence Over Time',
                                color_continuous_scale='Reds',
                                height=max(400, len(all_sections) * 20)  # Adjust height based on number of sections
                            )
                            
                            # Update layout for better readability
                            fig.update_layout(
                                yaxis_title="Section Name",
                                xaxis_title="Year",
                                yaxis={'categoryorder': 'array', 'categoryarray': ordered_sections}
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
