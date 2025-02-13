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
        "Opioid-induced hyperalgesia",
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
                        # Move controls to the right
                        _, controls_col1, controls_col2, controls_col3 = st.columns([3, 1, 1, 1])
                        with controls_col1:
                            zoom_level = st.slider("Zoom", 50, 200, 100, 10, 
                                                 label_visibility="collapsed",
                                                 key="unique_zoom_slider")
                        with controls_col2:
                            st.button("Fit to Screen", key="unique_fit_btn")
                        with controls_col3:
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
                                "📥",  # Using a more elegant download icon
                                data=csv_df.to_csv(index=False),
                                file_name="toc_history.csv",
                                mime="text/csv",
                                key="unique_download_btn",
                                help="Download data as CSV"
                            )
                        
                        # Timeline view styling
                        st.markdown(f"""
                            <style>
                                .stHorizontalBlock {{
                                    overflow-x: auto;
                                    padding: 1rem;
                                    background: white;
                                    border: 1px solid #e5e7eb;
                                    border-radius: 4px;
                                }}
                                [data-testid="column"] {{
                                    min-width: 300px;
                                    border-right: 1px solid #e5e7eb;
                                    padding: 1rem !important;
                                }}
                                .year-header {{
                                    font-size: {14 * zoom_level/100}px !important;
                                    font-weight: 600;
                                    margin-bottom: 1rem;
                                    padding-bottom: 0.5rem;
                                    border-bottom: 1px solid #e5e7eb;
                                    text-align: center;
                                }}
                                .section-container {{
                                    position: relative;
                                    padding: 2px 4px 2px 24px;
                                    margin: 2px 0;
                                }}
                                .section-title {{
                                    white-space: nowrap;
                                    overflow: hidden;
                                    text-overflow: ellipsis;
                                    padding: 2px 4px;
                                    border-radius: 4px;
                                    font-size: {13 * zoom_level/100}px;
                                    transition: all 0.2s;
                                    position: relative;
                                    z-index: 2;
                                }}
                                .section-title:hover {{
                                    background-color: #f3f4f6;
                                    white-space: normal;
                                }}
                                .section-new {{
                                    background-color: #dcfce7 !important;
                                }}
                                .vertical-line {{
                                    position: absolute;
                                    left: 12px;
                                    top: 0;
                                    bottom: 0;
                                    width: 2px;
                                    background-color: #e5e7eb;
                                    z-index: 1;
                                }}
                                /* Style for buttons */
                                .stButton button {{
                                    padding: 0.25rem 0.5rem;
                                    font-size: 0.875rem;
                                    border: 1px solid #e5e7eb;
                                    background-color: white;
                                    border-radius: 4px;
                                    display: flex;
                                    align-items: center;
                                    justify-content: center;
                                }}
                                .stButton button:hover {{
                                    background-color: #f3f4f6;
                                }}
                            </style>
                        """, unsafe_allow_html=True)
                        
                        # Create columns for each year
                        cols = st.columns(len(toc_history))
                        
                        # Display content in columns
                        prev_year_sections = set()  # Track sections from previous year
                        for idx, (year, sections) in enumerate(sorted(toc_history.items())):
                            with cols[idx]:
                                # Year header centered
                                st.markdown(f'<div class="year-header">{year}</div>', unsafe_allow_html=True)
                                
                                # Get current year's section titles
                                current_sections = {s["title"] for s in sections}
                                
                                # Process sections
                                for section in sections:
                                    level = section['level']
                                    
                                    # Check if section is new
                                    section['isNew'] = section['title'] not in prev_year_sections
                                    
                                    # Create vertical lines only for nested sections (level > 1)
                                    hierarchy_lines = ""
                                    if level > 1:
                                        hierarchy_lines = '<div class="vertical-line"></div>'
                                    
                                    # Add class for new sections
                                    section_class = "section-new" if section.get('isNew') else ""
                                    indent_style = f"margin-left: {(level-1) * 20}px" if level > 1 else ""
                                    
                                    st.markdown(
                                        f'<div class="section-container" style="{indent_style}">'
                                        f'{hierarchy_lines}'
                                        f'<div class="section-title {section_class}" title="{section["title"]}">'
                                        f'{section["title"]}'
                                        f'</div></div>',
                                        unsafe_allow_html=True
                                    )
                                
                                # Update previous year's sections
                                prev_year_sections = current_sections
                        
                        # Create columns for each year
                        cols = st.columns(len(toc_history))
                        
                        # Display content in columns
                        prev_year_sections = set()  # Track sections from previous year
                        for idx, (year, sections) in enumerate(sorted(toc_history.items())):
                            with cols[idx]:
                                # Year header
                                st.markdown(f'<div class="year-header">{year}</div>', unsafe_allow_html=True)
                                
                                # Get current year's section titles
                                current_sections = {s["title"] for s in sections}
                                
                                # Process sections
                                for section in sections:
                                    level = section['level']
                                    
                                    # Check if section is new (not in previous year)
                                    section['isNew'] = section['title'] not in prev_year_sections
                                    
                                    # Create vertical lines for hierarchy
                                    hierarchy_lines = ""
                                    if level > 1:
                                        hierarchy_lines = '<div class="vertical-line"></div>'
                                    
                                    # Add class for new sections
                                    section_class = "section-new" if section.get('isNew') else ""
                                    indent_style = f"margin-left: {(level-1) * 20}px"
                                    
                                    st.markdown(
                                        f'<div class="section-container" style="{indent_style}">'
                                        f'{hierarchy_lines}'
                                        f'<div class="section-title {section_class}" title="{section["title"]}">'
                                        f'{section["title"]}'
                                        f'</div></div>',
                                        unsafe_allow_html=True
                                    )
                                
                                # Update previous year's sections for next iteration
                                prev_year_sections = current_sections
                    
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
