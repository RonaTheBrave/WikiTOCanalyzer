import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import requests
from typing import Dict, List, Optional
import numpy as np
from difflib import SequenceMatcher

def get_revision_content(title: str, revid: Optional[str] = None) -> Optional[str]:
    """Fetch content of a specific revision or current version of a Wikipedia page"""
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

def get_page_history(title: str, start_year: int, end_year: int) -> List[Dict]:
    """Fetch list of revisions for a Wikipedia page within specified years"""
    api_url = "https://en.wikipedia.org/w/api.php"
    
    # Convert years to timestamps
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
    
    with st.spinner("Fetching revision history..."):
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

def extract_toc(wikitext: str) -> List[Dict]:
    """Extract table of contents from Wikipedia page content"""
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

def detect_renamed_sections(prev_sections: List[Dict], curr_sections: List[Dict]) -> Dict[str, str]:
    """Detect renamed sections using similarity metrics"""
    def similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    renamed_sections = {}
    prev_titles = {s["title"] for s in prev_sections}
    curr_titles = {s["title"] for s in curr_sections}
    
    removed_titles = prev_titles - curr_titles
    added_titles = curr_titles - prev_titles
    
    for old_title in removed_titles:
        best_match = None
        best_score = 0
        for new_title in added_titles:
            sim_score = similarity(old_title, new_title)
            if sim_score > 0.6 and sim_score > best_score:
                best_score = sim_score
                best_match = new_title
        
        if best_match:
            renamed_sections[best_match] = old_title
            st.write(f"Found rename: {old_title} → {best_match} (score: {best_score:.2f})")
    
    return renamed_sections

def process_revision_history(title: str, start_year: int, end_year: int) -> Dict:
    """Process revision history and extract TOC with rename detection"""
    revisions = get_page_history(title, start_year, end_year)
    
    yearly_revisions = {}
    years_processed = set()
    previous_sections = None
    
    for rev in reversed(revisions):
        year = datetime.strptime(rev['timestamp'], "%Y-%m-%dT%H:%M:%SZ").year
        
        if year not in years_processed and start_year <= year <= end_year:
            content = get_revision_content(title, rev['revid'])
            if content:
                sections = extract_toc(content)
                
                # Detect renames if we have previous data
                if previous_sections is not None:
                    renamed_sections = detect_renamed_sections(previous_sections, sections)
                    
                    # Mark renamed sections
                    for section in sections:
                        if section["title"] in renamed_sections:
                            section["isRenamed"] = True
                            section["previousTitle"] = renamed_sections[section["title"]]
                        elif previous_sections is None or section["title"] not in [s["title"] for s in previous_sections]:
                            section["isNew"] = True
                
                yearly_revisions[str(year)] = {
                    "sections": sections,
                    "revid": rev['revid']
                }
                previous_sections = sections
                years_processed.add(year)
    
    return yearly_revisions

def render_timeline(toc_history: Dict, zoom_level: int) -> str:
    """Render the complete timeline view with side-by-side columns"""
    timeline_html = f'<div class="timeline-container" style="transform: scale({zoom_level/100}); transform-origin: left top;">'
    
    for year, data in sorted(toc_history.items()):
        # Create column for each year
        timeline_html += '<div class="year-column">'
        
        # Year header with revision link if available
        revid = data.get("revid")
        year_link = f'<a href="https://en.wikipedia.org/w/index.php?oldid={revid}" target="_blank">{year}</a>' if revid else year
        timeline_html += f'<div class="year-header">{year_link}</div>'
        
        # Sections list
        timeline_html += '<div class="sections-list">'
        for section in data["sections"]:
            # Determine section classes
            classes = ["section-title"]
            if section.get("isNew"):
                classes.append("section-new")
            if section.get("isRenamed"):
                classes.append("section-renamed")
            
            # Add indentation based on level
            indent_class = f"level-{section.get('level', 1)}"
            classes.append(indent_class)
            
            # Compose section HTML
            section_html = f'<div class="{" ".join(classes)}">'
            section_html += section["title"]
            if section.get("isRenamed"):
                section_html += f' <span class="rename-note">(was: {section["previousTitle"]})</span>'
            section_html += '</div>'
            
            timeline_html += section_html
        
        timeline_html += '</div></div>'  # Close sections-list and year-column
    
    timeline_html += '</div>'  # Close timeline-container
    return timeline_html
    
    # Add year columns
    for year in years:
        revid = toc_history[year].get("revid")
        year_link = f'<a href="https://en.wikipedia.org/w/index.php?oldid={revid}" target="_blank">{year}</a>' if revid else year
        table_html += f'<th class="year-header">{year_link}</th>'
    
    table_html += '</tr></thead><tbody>'
    
    # Add rows for each section
    for section in sorted(all_sections):
        table_html += '<tr>'
        
        # Find first occurrence of section to get its level
        section_level = None
        for year_data in toc_history.values():
            for s in year_data["sections"]:
                if s["title"] == section:
                    section_level = s.get("level", 1)
                    break
            if section_level:
                break
        
        # Add section name and level
        indent = '&nbsp;' * ((section_level or 1) - 1) * 4
        table_html += f'<td class="section-name">{indent}{section}</td>'
        table_html += f'<td class="section-level">{"*" * (section_level or 1)}</td>'
        
        # Add cells for each year
        for year in years:
            cell_classes = ["section-cell"]
            cell_content = ""
            
            # Find section in this year's data
            year_data = toc_history[year]
            section_exists = False
            section_info = None
            
            for s in year_data["sections"]:
                if s["title"] == section:
                    section_exists = True
                    section_info = s
                    break
            
            if section_exists:
                if section_info.get("isNew"):
                    cell_classes.append("section-new")
                elif section_info.get("isRenamed"):
                    cell_classes.append("section-renamed")
                cell_content = "●"
            
            cell_class_str = ' '.join(cell_classes)
            table_html += f'<td class="{cell_class_str}">{cell_content}</td>'
        
        table_html += '</tr>'
    
    table_html += '</tbody></table></div>'
    return table_html

# Main application code
st.set_page_config(page_title="Wikipedia TOC History Viewer", layout="wide")

# Custom CSS (same as before)
st.markdown("""
<style>
    /* ... (previous CSS remains the same) ... */
</style>
""", unsafe_allow_html=True)

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
        
        # Year range selection
        current_year = datetime.now().year
        col1, col2 = st.columns(2)
        with col1:
            start_year = st.number_input("Start Year", min_value=2001, max_value=current_year-1, value=2019)
        with col2:
            end_year = st.number_input("End Year", min_value=start_year+1, max_value=current_year, value=min(start_year+5, current_year))
            
        show_renames = st.toggle(
            "Enable Rename Detection",
            True,
            help="Detect and highlight renamed sections"
        )
    
    if wiki_page:
        view_mode = st.radio(
            "View Mode",
            ["Timeline View", "Edit Activity", "Section Count"],
            horizontal=True,
            key="view_mode"
        )
        
        try:
            with st.spinner("Analyzing page history..."):
                toc_history = process_revision_history(wiki_page, start_year, end_year)
                
                if toc_history:
                    st.success(f"Found historical versions from {len(toc_history)} different years")
                    
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
                    
                    # Legend
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
                            </div>
                        """, unsafe_allow_html=True)
                    
                    # View content
                    if view_mode == "Timeline View":
                        timeline_html = render_timeline(toc_history, zoom_level)
                        st.markdown(timeline_html, unsafe_allow_html=True)
                    
                    elif view_mode == "Section Count":
                        fig = create_section_count_chart(toc_history)
                        st.plotly_chart(fig, use_container_width=True)
                    
                    elif view_mode == "Edit Activity":
                        st.info("Edit Activity view is coming soon!")
                else:
                    st.warning("No historical versions found in the selected year range.")
                    
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.info("Please check if the Wikipedia page title is correct and try again.")

if __name__ == "__main__":
    main()
