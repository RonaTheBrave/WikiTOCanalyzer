import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
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
        "rvprop": "ids|timestamp|content",
        "rvlimit": "500",
        "formatversion": "2",
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
    Extract table of contents from Wikipedia page content with proper level handling.
    """
    sections = []
    current_level_stack = []
    
    try:
        lines = wikitext.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('==') and line.endswith('=='):
                title = line.strip('=').strip()
                raw_level = (len(line) - len(title)) // 2
                
                # Ensure proper level hierarchy
                if not current_level_stack or raw_level > current_level_stack[-1]:
                    level = len(current_level_stack) + 1
                    current_level_stack.append(raw_level)
                else:
                    while current_level_stack and raw_level <= current_level_stack[-1]:
                        current_level_stack.pop()
                    level = len(current_level_stack) + 1
                    current_level_stack.append(raw_level)
                
                if title:
                    sections.append({
                        "title": title,
                        "level": level,
                        "raw_level": raw_level
                    })
    except Exception as e:
        st.error(f"Error extracting sections: {str(e)}")
    return sections

def detect_renamed_sections(prev_sections, curr_sections):
    """
    Detect renamed sections using similarity metrics
    """
    from difflib import SequenceMatcher
    
    def similarity(a, b):
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    renamed_sections = {}
    removed_sections = prev_sections - curr_sections
    added_sections = curr_sections - prev_sections
    
    for old_section in removed_sections:
        best_match = None
        best_score = 0
        for new_section in added_sections:
            sim_score = similarity(old_section, new_section)
            if sim_score > 0.6 and sim_score > best_score:
                best_score = sim_score
                best_match = new_section
        
        if best_match:
            renamed_sections[best_match] = old_section
            print(f"Found rename: {old_section} -> {best_match} (score: {best_score})")
    
    return renamed_sections

def process_revision_history(title):
    """
    Process revision history and extract TOC
    """
    revisions = get_page_history(title)
    
    yearly_revisions = {}
    years_processed = set()
    previous_sections = None
    
    for rev in reversed(revisions):
        year = datetime.strptime(rev['timestamp'], "%Y-%m-%dT%H:%M:%SZ").year
        
        if year not in years_processed and year >= 2019:
            content = get_revision_content(title, rev['revid'])
            if content:
                sections = extract_toc(content)
                current_sections = {s["title"] for s in sections}
                
                renamed_sections = {}
                removed_sections = set()
                if previous_sections is not None:
                    renamed_sections = detect_renamed_sections(previous_sections, current_sections)
                    removed_sections = previous_sections - current_sections - set(renamed_sections.values())
                
                for section in sections:
                    section_title = section["title"]
                    if previous_sections is None or section_title not in previous_sections:
                        if section_title in renamed_sections:
                            section["isRenamed"] = True
                            section["previousTitle"] = renamed_sections[section_title]
                        else:
                            section["isNew"] = True
                
                data = {
                    "sections": sections,
                    "removed": removed_sections,
                    "renamed": renamed_sections
                }
                
                yearly_revisions[str(year)] = data
                previous_sections = current_sections
                years_processed.add(year)
    
    return yearly_revisions

def create_section_count_chart(toc_history):
    """
    Create section count visualization
    """
    counts = []
    for year, data in sorted(toc_history.items()):
        total = len(data["sections"])
        new = len([s for s in data["sections"] if s.get("isNew", True)])
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
    
    show_renames = st.toggle("Enable Rename Detection", True,
                           help="When enabled, detects and highlights sections that were renamed")

if wiki_page:
    try:
        with st.spinner("Analyzing page history..."):
            current_content = get_revision_content(wiki_page)
            if current_content:
                st.success("Successfully retrieved current version")
                current_sections = extract_toc(current_content)
                
                toc_history = process_revision_history(wiki_page)
                
                if toc_history:
                    st.success(f"Found historical versions from {len(toc_history)} different years")
                    
                    rename_summary = []
                    for year, data in sorted(toc_history.items()):
                        if data.get("renamed"):
                            for new_name, old_name in data["renamed"].items():
                                rename_summary.append(f"{year}: '{old_name}' → '{new_name}'")
                    
                    if rename_summary:
                        with st.expander("Section Renames Detected"):
                            for rename in rename_summary:
                                st.write(rename)
                    
                    view_mode = st.radio(
                        "View Mode",
                        ["Timeline View", "Edit Activity", "Section Count"],
                        horizontal=True,
                        key="view_mode"
                    )
                    
                    if view_mode == "Timeline View":
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
                                    position: sticky;
                                    top: 0;
                                    background: white;
                                    z-index: 10;
                                }}
                                .section-container {{
                                    position: relative;
                                    padding: 2px 4px 2px 24px;
                                    margin: 2px 0;
                                }}
                                .section-title {{
                                    display: block;
                                    white-space: nowrap;
                                    overflow: hidden;
                                    text-overflow: ellipsis;
                                    padding: 2px 4px;
                                    border-radius: 4px;
                                    font-size: {13 * zoom_level/100}px;
                                    transition: all 0.2s;
                                    position: relative;
                                    z-index: 2;
                                    max-width: 100%;
                                    box-sizing: border-box;
                                }}
                                .section-title:hover {{
                                    background-color: #f3f4f6;
                                    white-space: normal;
                                    z-index: 3;
                                }}
                                .section-new {{
                                    background-color: #dcfce7 !important;
                                }}
                                .section-renamed {{
                                    background-color: #fef3c7 !important;
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
                            </style>
                        """, unsafe_allow_html=True)
                        
                        # Controls for zoom and export
                        zoom_level = st.slider("Zoom", 50, 200, 100, 10)
                        
                        # Display timeline columns
                        cols = st.columns(len(toc_history))
                        for idx, (year, data) in enumerate(sorted(toc_history.items())):
                            with cols[idx]:
                                st.markdown(f'<div class="year-header">{year}</div>', 
                                          unsafe_allow_html=True)
                                
                                for section in data["sections"]:
                                    indent = "&nbsp;" * (4 * (section["level"] - 1))
                                    classes = []
                                    if section.get("isNew"):
                                        classes.append("section-new")
                                    if show_renames and section.get("isRenamed"):
                                        classes.append("section-renamed")
                                    
                                    class_str = " ".join(classes)
                                    
                                    st.markdown(f"""
                                        <div class="section-container">
                                            {indent}<span class="section-title {class_str}">
                                                {section["title"]}
                                            </span>
                                        </div>
                                    """, unsafe_allow_html=True)
                                
                                if "removed" in data:
                                    for removed_section in data["removed"]:
                                        st.markdown(f"""
                                            <div class="section-container">
                                                <span class="section-title" style="background-color: #fee2e2;">
                                                    {removed_section}
                                                </span>
                                            </div>
                                        """, unsafe_allow_html=True)
                    
                    elif view_mode == "Edit Activity":
                        st.write("Edit Activity view coming soon!")
                    
                    elif view_mode == "Section Count":
                        fig = create_section_count_chart(toc_history)
                        st.plotly_chart(fig, use_container_width=True)
                
                else:
                    st.warning("No historical versions found.")
            else:
                st.error("Could not retrieve page content.")

    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.info("Please check if the Wikipedia page title is correct and try again.")
