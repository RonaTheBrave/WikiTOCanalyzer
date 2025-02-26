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
                if 'missing' in page:
                    st.error(f"Page '{title}' not found on Wikipedia")
                    break
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
    Enhanced detection of renamed sections with better similarity metrics 
    and hierarchy awareness
    """
    from difflib import SequenceMatcher
    
    def similarity(a, b):
        # More sophisticated similarity that considers length differences
        ratio = SequenceMatcher(None, a.lower(), b.lower()).ratio()
        
        # Adjust ratio based on length differences to prevent matching very short/long sections
        len_diff_factor = min(len(a), len(b)) / max(len(a), len(b)) if max(len(a), len(b)) > 0 else 0
        
        # Higher weight to exact prefix/suffix matches (common in section renames)
        prefix_match = min(3, min(len(a), len(b))) if a[:min(3, len(a))].lower() == b[:min(3, len(b))].lower() else 0
        
        adjusted_score = ratio * 0.8 + len_diff_factor * 0.1 + (prefix_match / 3) * 0.1
        return adjusted_score

    # Extract section titles only (no level info at this stage)
    prev_titles = {s for s in prev_sections}
    curr_titles = {s for s in curr_sections}
    
    # Sections that are exact matches
    exact_matches = prev_titles.intersection(curr_titles)
    
    # Create mapping of lowercase to original case for remaining sections
    prev_case_map = {s.lower(): s for s in prev_titles - exact_matches}
    curr_case_map = {s.lower(): s for s in curr_titles - exact_matches}
    
    # Find sections that differ only in case
    case_renames = {}
    for s_lower in set(prev_case_map.keys()) & set(curr_case_map.keys()):
        if prev_case_map[s_lower] != curr_case_map[s_lower]:
            case_renames[curr_case_map[s_lower]] = prev_case_map[s_lower]
    
    # Find other renamed sections using similarity
    removed_titles = prev_titles - exact_matches - set(case_renames.values())
    added_titles = curr_titles - exact_matches - set(case_renames.keys())
    
    renamed_sections = case_renames.copy()
    
    # Use a more robust approach for identifying similar titles
    for old_title in removed_titles:
        candidates = []
        for new_title in added_titles:
            sim_score = similarity(old_title, new_title)
            if sim_score > 0.65:  # Slightly higher threshold for better precision
                candidates.append((new_title, sim_score))
        
        if candidates:
            # Sort by similarity score
            candidates.sort(key=lambda x: x[1], reverse=True)
            best_match, score = candidates[0]
            
            # Log for debugging (remove in production or use a debug flag)
            # print(f"Potential rename: '{old_title}' → '{best_match}' (score: {score:.2f})")
            
            renamed_sections[best_match] = old_title
            added_titles.remove(best_match)  # Remove to prevent multiple matches
    
    return renamed_sections
    
def process_revision_history(title):
    """
    Process revision history and extract TOC with enhanced path tracking
    """
    revisions = get_page_history(title)
    
    yearly_revisions = {}
    years_processed = set()
    previous_sections = None
    previous_section_paths = {}  # Track full section paths
    
    for rev in reversed(revisions):
        year = datetime.strptime(rev['timestamp'], "%Y-%m-%dT%H:%M:%SZ").year
        
        if year not in years_processed and year >= 2019:
            content = get_revision_content(title, rev['revid'])
            if content:
                sections = extract_toc(content)
                current_sections = {s["title"] for s in sections}
                
                # Build current section paths
                current_section_paths = {}
                
                # First pass: find all level 1 sections
                level1_sections = [s for s in sections if s["level"] == 1]
                
                # Second pass: assign paths
                for section in sections:
                    if section["level"] == 1:
                        # Top-level sections have their name as path
                        current_section_paths[section["title"]] = section["title"]
                    else:
                        # Find the most recent parent section
                        parent_idx = -1
                        for i, s in enumerate(sections):
                            idx = sections.index(section)
                            if i < idx and s["level"] < section["level"]:
                                parent_idx = i
                        
                        if parent_idx >= 0:
                            parent = sections[parent_idx]
                            parent_path = current_section_paths.get(parent["title"], parent["title"])
                            current_section_paths[section["title"]] = f"{parent_path} > {section['title']}"
                        else:
                            # Fallback if we can't find a parent
                            current_section_paths[section["title"]] = section["title"]
                
                # Detect renamed sections
                renamed_sections = {}
                removed_sections = set()
                
                if previous_sections is not None:
                    # Basic rename detection based on titles
                    renamed_sections = detect_renamed_sections(previous_sections, current_sections)
                    
                    # Further refine based on paths
                    for new_title, old_title in list(renamed_sections.items()):
                        if old_title in previous_section_paths and new_title in current_section_paths:
                            old_path = previous_section_paths[old_title]
                            new_path = current_section_paths[new_title]
                            
                            # If paths are completely different, maybe it's not a rename
                            if '>' in old_path and '>' in new_path:
                                old_parent = old_path.split(' > ')[0]
                                new_parent = new_path.split(' > ')[0]
                                
                                # If parents are different and not similar, probably not a rename
                                if old_parent != new_parent and SequenceMatcher(None, old_parent.lower(), new_parent.lower()).ratio() < 0.5:
                                    del renamed_sections[new_title]
                    
                    removed_sections = previous_sections - current_sections - set(renamed_sections.values())
                
                # Mark sections as new or renamed
                for section in sections:
                    section_title = section["title"]
                    # Assign path to section for visualization
                    section["path"] = current_section_paths.get(section_title, section_title)
                    
                    if previous_sections is None or section_title not in previous_sections:
                        if section_title in renamed_sections:
                            section["isRenamed"] = True
                            section["previousTitle"] = renamed_sections[section_title]
                            # Store the full path history
                            if renamed_sections[section_title] in previous_section_paths:
                                section["previousPath"] = previous_section_paths[renamed_sections[section_title]]
                        else:
                            section["isNew"] = True
                
                data = {
                    "sections": sections,
                    "removed": removed_sections,
                    "renamed": renamed_sections,
                    "paths": current_section_paths
                }
                
                yearly_revisions[str(year)] = data
                previous_sections = current_sections
                previous_section_paths = current_section_paths
                years_processed.add(year)
    
    return yearly_revisions
    
def create_section_count_chart(toc_history):
    """
    Create section count visualization with level breakdown
    """
    data = []
    for year, content in sorted(toc_history.items()):
        level_counts = {}
        for section in content["sections"]:
            level = section["level"]
            level_counts[f"Level {level}"] = level_counts.get(f"Level {level}", 0) + 1
        
        row = {"Year": year}
        row.update(level_counts)
        data.append(row)
    
    df = pd.DataFrame(data)
    
    # Create stacked bar chart
    fig = go.Figure()
    for level in [col for col in df.columns if col.startswith("Level ")]:
        fig.add_trace(go.Bar(
            name=level,
            x=df["Year"],
            y=df[level],
            hovertemplate="Count %{y}<extra></extra>"
        ))
    
    fig.update_layout(
        title="Section Count by Level",
        xaxis_title="Year",
        yaxis_title="Number of Sections",
        barmode='stack',
        showlegend=True,
        hovermode='x'
    )
    
    return fig

def calculate_edit_activity(revisions, title, toc_history=None):
    """
    Calculate edit activity for each section across years with improved case handling
    Returns: Dictionary mapping sections to their edit history
    """
    section_edits = {}
    section_first_seen = {}
    rename_history = {}  # Track rename history
    
    # Dictionary for case-insensitive handling (maps lowercase section titles to actual titles)
    case_map = {}

    # Build rename history from toc_history if provided
    if toc_history:
        for year, data in sorted(toc_history.items()):
            if "renamed" in data:
                for new_name, old_name in data["renamed"].items():
                    if new_name.lower() not in rename_history:
                        rename_history[new_name.lower()] = []
                    rename_history[new_name.lower()].append((old_name, year))

    # Process revisions in chronological order
    for rev in reversed(revisions):  # Reversed to match Timeline view's order
        year = datetime.strptime(rev['timestamp'], "%Y-%m-%dT%H:%M:%SZ").year
        year_str = str(year)
        
        content = get_revision_content(title, rev['revid'])
        if content:
            sections = extract_toc(content)
            
            # Update edit counts and track renames
            for section in sections:
                section_title = section["title"]
                level = "*" * section["level"]
                
                # Case-insensitive key for lookups
                section_key = section_title.lower()
                
                # Update case map with the current capitalization
                case_map[section_key] = section_title
                
                # Check if this is a renamed section
                if section.get("isRenamed"):
                    old_title = section["previousTitle"]
                    old_key = old_title.lower()
                    
                    # Update rename history
                    if section_key not in rename_history:
                        rename_history[section_key] = [(old_title, year_str)]
                    
                    # Transfer data from old section to new (case-insensitive)
                    if old_key in section_edits:
                        if section_key not in section_edits:
                            section_edits[section_key] = section_edits[old_key].copy()
                            section_edits[section_key]["section"] = section_title  # Use current capitalization
                            section_first_seen[section_key] = section_first_seen.get(old_key, year_str)
                        del section_edits[old_key]
                
                # Initialize or update section data
                if section_key not in section_edits:
                    section_edits[section_key] = {
                        "section": section_title,  # Use original capitalization
                        "level": level,
                        "edits": {},
                        "totalEdits": 0,
                        "first_seen": year_str,
                        "rename_history": rename_history.get(section_key, [])
                    }
                    section_first_seen[section_key] = year_str
                else:
                    # Update the capitalization to the most recent one
                    section_edits[section_key]["section"] = section_title
                
                # Increment edit count for this year
                if year_str not in section_edits[section_key]["edits"]:
                    section_edits[section_key]["edits"][year_str] = 0
                section_edits[section_key]["edits"][year_str] += 1
                section_edits[section_key]["totalEdits"] += 1

    # Format data for visualization
    formatted_data = []
    for key, data in section_edits.items():
        first_year = data["first_seen"]
        lifespan = f"{first_year}-present"
        
        formatted_data.append({
            "section": data["section"],  # Use the most recent capitalization
            "level": data["level"],
            "edits": data["edits"],
            "lifespan": lifespan,
            "totalEdits": data["totalEdits"],
            "rename_history": data.get("rename_history", [])
        })

    return sorted(formatted_data, key=lambda x: x['section'].lower())  # Sort by lowercase name for consistency


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
    
    # Enhanced rename detection controls
    st.subheader("Rename Detection")
    show_renames = st.toggle("Enable Rename Detection", True,
                           help="When enabled, detects and highlights sections that were renamed")
    
    if show_renames:
        rename_sensitivity = st.slider(
            "Rename Detection Sensitivity", 
            min_value=0.5, 
            max_value=0.9, 
            value=0.65, 
            step=0.05,
            format="%.2f",
            help="Higher values require more similarity between section titles to be considered a rename"
        )
        
        # Update the similarity threshold dynamically
        if 'rename_sensitivity' in locals():
            # We need to modify the detect_renamed_sections function to use this threshold
            # This is a bit hacky, but we can use it as a global variable
            st.session_state.rename_threshold = rename_sensitivity
    
    st.divider()  # Add a visual separator
    
    view_mode = st.radio(
        "Analysis Mode",
        ["Timeline View", "Edit Activity", "Section Count"],
        key="view_mode"
    )
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
                    
                    # Add debug viewing of renames
                    if 'debug_mode' not in st.session_state:
                        st.session_state.debug_mode = False
                        
                    if toc_history and st.session_state.get('debug_mode', False):
                        with st.expander("Debug: Rename Detection Analysis"):
                            # Display all detected renames
                            st.subheader("Detected Renames by Year")
                            for year, data in sorted(toc_history.items()):
                                if data.get("renamed"):
                                    st.write(f"**Year: {year}**")
                                    for new_name, old_name in data["renamed"].items():
                                        # Calculate similarity for debugging
                                        from difflib import SequenceMatcher
                                        similarity_score = SequenceMatcher(None, old_name.lower(), new_name.lower()).ratio()
                                        st.write(f"- '{old_name}' → '{new_name}' (similarity: {similarity_score:.2f})")
                                        
                                        # If we have path information, show it
                                        if "paths" in data and new_name in data["paths"]:
                                            new_path = data["paths"][new_name]
                                            st.write(f"  Path: {new_path}")
                                else:
                                    st.write(f"**Year: {year}** - No renames detected")
                    
                    if view_mode == "Timeline View":
                        color = "#000000"  # Define color in case it's referenced
                        background = "white"  # Define background in case it's referenced
                        
                        # Controls section
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            zoom_level_raw = st.slider("Zoom", 50, 200, 100, 10)
                            zoom_level = float(zoom_level_raw)  # Ensure it's a number
                    
                        with col2:
                            # Prepare CSV data
                            csv_data = []
                            for year, data in sorted(toc_history.items()):
                                for section in data["sections"]:
                                    csv_data.append({
                                        'Year': year,
                                        'Section': section['title'],
                                        'Level': section['level'],
                                        'Status': 'New' if section.get('isNew') else 'Existing'
                                    })
                            csv_df = pd.DataFrame(csv_data)
                            st.download_button(
                                "↓",
                                data=csv_df.to_csv(index=False),
                                file_name="toc_history.csv",
                                mime="text/csv",
                                help="Download data as CSV"
                            )

                        # Add legend
                        st.markdown("""
                            <div style="display: flex; gap: 1rem; margin-bottom: 1rem; font-size: 0.875rem;">
                                <div style="display: flex; align-items: center; gap: 0.5rem;">
                                    <div style="width: 12px; height: 12px; border-radius: 3px; background-color: #dcfce7;"></div>
                                    <span>New sections</span>
                                </div>
                                <div style="display: flex; align-items: center; gap: 0.5rem;">
                                    <div style="width: 12px; height: 12px; border-radius: 3px; background-color: #fef3c7;"></div>
                                    <span>Renamed sections</span>
                                </div>
                                <div style="display: flex; align-items: center; gap: 0.5rem;">
                                    <div style="width: 12px; height: 12px; border-radius: 3px; background-color: #fee2e2;"></div>
                                    <span>Sections to be removed</span>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)

                        # Define the dynamic styles separately
                        year_header_font_size = f"font-size: {14 * float(zoom_level)/100}px;"
                        section_title_font_size = f"font-size: {13 * float(zoom_level)/100}px;"
                        
                        # Now use a normal string for the CSS with placeholders
                        css = """
                        <style>
                            .stHorizontalBlock {
                                overflow-x: auto;
                                padding: 1rem;
                                background-color: white;
                                border: 1px solid #e5e7eb;
                                border-radius: 4px;
                            }
                            [data-testid="column"] {
                                min-width: 300px;
                                max-width: 300px;
                                border-right: 1px solid #e5e7eb;
                                padding: 1rem !important;
                                overflow: hidden;
                            }
                            .year-header {
                                YEAR_HEADER_FONT_SIZE
                                font-weight: 600;
                                margin-bottom: 1rem;
                                padding-bottom: 0.5rem;
                                border-bottom: 1px solid #e5e7eb;
                                text-align: center;
                                position: sticky;
                                top: 0;
                                background-color: white;
                                z-index: 10;
                            }
                            .section-container {
                                position: relative;
                                padding: 2px 4px 2px 24px;
                                margin: 2px 0;
                                overflow: hidden;
                                width: 100%;
                                box-sizing: border-box;
                            }
                            .section-title {
                                display: block;
                                white-space: nowrap;
                                overflow: hidden;
                                text-overflow: ellipsis;
                                padding: 2px 4px;
                                border-radius: 4px;
                                SECTION_TITLE_FONT_SIZE
                                transition: all 0.2s;
                                position: relative;
                                z-index: 2;
                                max-width: 100%;
                                box-sizing: border-box;
                            }
                            .section-title:hover {
                                background-color: #f3f4f6;
                                white-space: normal;
                                z-index: 3;
                                position: relative;
                                overflow: visible;
                            }
                            .section-new {
                                background-color: #dcfce7 !important;
                            }
                            .section-renamed {
                                background-color: #fef3c7 !important;
                            }
                            .vertical-line {
                                position: absolute;
                                left: 12px;
                                top: 0;
                                bottom: 0;
                                width: 2px;
                                background-color: #e5e7eb;
                                z-index: 1;
                            }
                            
                            /* Additional containment styles */
                            .streamlit-expanderContent {
                                overflow: hidden;
                            }
                            [data-testid="stHorizontalBlock"] {
                                overflow-x: auto !important;
                            }
                            .rename-indicator {
                                display: inline-block;
                                font-size: 0.75em;
                                color: #9333ea;
                                margin-left: 4px;
                                cursor: help;
                            }
                            .tooltip {
                                position: relative;
                                display: inline-block;
                            }
                            .tooltip .tooltiptext {
                                visibility: hidden;
                                width: 180px;
                                background-color: #555;
                                color: #fff;
                                text-align: center;
                                border-radius: 4px;
                                padding: 5px;
                                position: absolute;
                                z-index: 100;
                                bottom: 125%;
                                left: 50%;
                                margin-left: -90px;
                                opacity: 0;
                                transition: opacity 0.3s;
                                font-size: 10px;
                                white-space: normal;
                            }
                            .tooltip:hover .tooltiptext {
                                visibility: visible;
                                opacity: 1;
                            }
                        </style>
                        """
                        
                        # Replace the placeholders
                        css = css.replace('YEAR_HEADER_FONT_SIZE', year_header_font_size)
                        css = css.replace('SECTION_TITLE_FONT_SIZE', section_title_font_size)
                        
                        # Apply the CSS
                        st.markdown(css, unsafe_allow_html=True)
                        
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
                                    
                                    # Different display for renamed sections
                                    if show_renames and section.get("isRenamed"):
                                        previous_title = section.get("previousTitle", "Unknown")
                                        st.markdown(f"""
                                            <div class="section-container">
                                                {indent}<span class="section-title {class_str} tooltip">
                                                    {section["title"]}
                                                    <span class="rename-indicator">↺</span>
                                                    <span class="tooltiptext">Renamed from: {previous_title}</span>
                                                </span>
                                            </div>
                                        """, unsafe_allow_html=True)
                                    else:
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
                        # Define constants first
                        max_edits = 15

                        # Color scaling function
                        def get_color(value, max_edits=15):
                            intensity = value / max_edits
                            rgb_value = round(255 * (1 - intensity))
                            return f'rgb(255, {rgb_value}, {rgb_value})'
                        
                        # Get real edit activity data
                        revisions = get_page_history(wiki_page)
                        st.write("Calculating edit activity...")
                        edit_data = calculate_edit_activity(revisions, wiki_page, toc_history)
                        
                        if not edit_data:
                            st.warning("No edit activity data found.")
                        else:
                            # Get all years from the data FIRST
                            all_years = set()
                            for item in edit_data:
                                all_years.update(item["edits"].keys())
                            years = sorted(list(all_years))

                            # Then add controls row
                            col1, col2 = st.columns([6, 1])
                            with col2:
                                st.button("⟲ Fit", key="fit_table", help="Fit table to screen width")
                            with col1:
                                # Prepare CSV data
                                csv_data = []
                                for row in edit_data:
                                    csv_row = {
                                        'Section': row['section'],
                                        'Level': row['level'],
                                        'Lifespan': row['lifespan'],
                                        'Total Edits': row['totalEdits']
                                    }
                                    # Add year columns
                                    for year in years:
                                        csv_row[year] = row['edits'].get(year, 'N/A')
                                    csv_data.append(csv_row)
                                csv_df = pd.DataFrame(csv_data)
                                st.download_button(
                                    "↓ Download Data",
                                    data=csv_df.to_csv(index=False),
                                    file_name="section_edits.csv",
                                    mime="text/csv",
                                    help="Download data as CSV"
                                )
                            
                            # Display color scale legend
                            st.markdown("""
                                <style>
                                    .edit-scale {
                                        display: flex;
                                        align-items: center;
                                        gap: 8px;
                                        margin-bottom: 16px;
                                    }
                                    .edit-gradient {
                                        display: flex;
                                        height: 16px;
                                        width: 128px;
                                    }
                                    .edit-gradient-box {
                                        flex: 1;
                                    }
                                </style>
                            """, unsafe_allow_html=True)
                            
                            st.markdown(
                                '<div class="edit-scale">Edit frequency: <span>0</span><div class="edit-gradient">' +
                                ''.join([f'<div class="edit-gradient-box" style="background-color: {get_color((max_edits/7)*i)}"></div>' for i in range(8)]) +
                                f'</div><span>{max_edits}+</span></div>',
                                unsafe_allow_html=True
                            )

                            # Add control buttons row
                            controls_col1, controls_col2, controls_col3, _ = st.columns([1, 1, 2, 4])
                            with controls_col1:
                                st.button("⟲ Fit", key="fit_table_ea", help="Fit table to screen width")
                            with controls_col2:
                                st.button("💾", key="save_table", help="Save as image")
                            with controls_col3:
                                sort_by = st.selectbox(
                                    "Sort by",
                                    ["Section Name", "Total Edits", "First Appearance"],
                                    key="sort_heatmap"
                                )

                            # Sort data based on selection
                            if sort_by == "Section Name":
                                edit_data = sorted(edit_data, key=lambda x: x['section'].lower())
                            elif sort_by == "Total Edits":
                                edit_data = sorted(edit_data, key=lambda x: x['totalEdits'], reverse=True)
                            elif sort_by == "First Appearance":
                                edit_data = sorted(edit_data, key=lambda x: x['lifespan'].split('-')[0])

                            # Create table
                            st.markdown("""
                                <style>
                                    .edit-table {
                                        width: 100%;
                                        border-collapse: collapse;
                                    }
                                    .edit-table th, .edit-table td {
                                        padding: 8px;
                                        text-align: center;
                                        border: 1px solid #e5e7eb;
                                    }
                                    .edit-table th {
                                        background-color: #f9fafb;
                                        font-weight: 500;
                                    }
                                    .edit-cell {
                                        border-radius: 4px;
                                        padding: 4px 8px;
                                    }
                                </style>
                            """, unsafe_allow_html=True)
                            
                            # Add rename chain styles
                            st.markdown("""
                                <style>
                                    /* Basic rename styles */
                                    .rename-chain {
                                        color: #9333ea;
                                        font-size: 0.8em;
                                        margin-top: 2px;
                                        padding-left: 12px;
                                        border-left: 2px solid #e5e7eb;
                                    }
                                    .rename-step {
                                        display: block;
                                        padding: 2px 0;
                                    }
                                    .rename-arrow {
                                        color: #9333ea;
                                        margin-right: 4px;
                                    }
                                    
                                    /* Enhanced rename history styles */
                                    .section-row.has-renames {
                                        background-color: #fcfaff !important;
                                    }
                                    .section-row.has-renames:hover {
                                        background-color: #f7f2fb !important;
                                    }
                                    .rename-indicator {
                                        display: inline-block;
                                        font-size: 0.9em;
                                        color: #9333ea;
                                        margin-left: 4px;
                                        cursor: help;
                                        font-weight: bold;
                                    }
                                    .rename-history {
                                        display: block;
                                        margin-top: 8px;
                                        padding: 6px 8px;
                                        border-left: 3px solid #d8b4fe;
                                        background-color: #f9f5ff;
                                        border-radius: 0 4px 4px 0;
                                        font-size: 0.85em;
                                        max-width: 250px;
                                        overflow-wrap: break-word;
                                    }
                                    .rename-history-header {
                                        font-weight: 500;
                                        color: #7e22ce;
                                        margin-bottom: 4px;
                                    }
                                    .rename-entry {
                                        padding: 2px 0;
                                        color: #6b21a8;
                                    }
                                    .old-name {
                                        font-style: italic;
                                        font-weight: 500;
                                    }
                                    
                                    /* Similarity score styles */
                                    .similarity-score {
                                        display: inline-block;
                                        padding: 1px 4px;
                                        border-radius: 3px;
                                        font-size: 0.8em;
                                        margin-left: 4px;
                                    }
                                    .high-similarity {
                                        background-color: #dcfce7;
                                        color: #166534;
                                    }
                                    .medium-similarity {
                                        background-color: #fef3c7;
                                        color: #92400e;
                                    }
                                    .low-similarity {
                                        background-color: #fee2e2;
                                        color: #991b1b;
                                    }
                                </style>
                            """, unsafe_allow_html=True)
                            
                            table_html = """
                                <div style="overflow-x: auto;">
                                <table class="edit-table">
                                    <thead>
                                        <tr>
                                            <th style="text-align: left;">Section</th>
                                            <th style="text-align: left;">Level</th>
                            """
                            
                            # Add year columns
                            for year in years:
                                table_html += f'<th>{year}</th>'
                            
                            table_html += """
                                            <th style="text-align: left;">Lifespan</th>
                                            <th style="text-align: center;">Total Edits</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                            """
                            
                            
                            # Add data rows
                            for row in edit_data:
                                # Add rename history indicator if exists
                                rename_info = ""
                                if row.get('rename_history') and len(row.get('rename_history', [])) > 0:
                                    # Create a more detailed and visible rename history display
                                    rename_info = '<div class="rename-history">'
                                    rename_info += '<div class="rename-history-header">Section name history:</div>'
                                    
                                    # Sort rename history by year (newest first)
                                    sorted_history = sorted(row['rename_history'], key=lambda x: x[1], reverse=True)
                                    
                                    for i, (old_name, year) in enumerate(sorted_history):
                                        # Calculate similarity score for research purposes
                                        from difflib import SequenceMatcher
                                        similarity = SequenceMatcher(None, old_name.lower(), row["section"].lower()).ratio()
                                        similarity_pct = round(similarity * 100)
                                        
                                        # Add similarity score indicator
                                        similarity_class = "high-similarity" if similarity > 0.8 else "medium-similarity" if similarity > 0.6 else "low-similarity"
                                        
                                        if i < len(sorted_history) - 1:
                                            # Not the oldest rename
                                            rename_info += f'<div class="rename-entry">{year}: Changed from "<span class="old-name">{old_name}</span>" '
                                            rename_info += f'<span class="similarity-score {similarity_class}" title="Text similarity between old and new names">{similarity_pct}% match</span></div>'
                                        else:
                                            # The oldest rename (original name)
                                            rename_info += f'<div class="rename-entry">{year}: Originally created as "<span class="old-name">{old_name}</span>" '
                                            rename_info += f'<span class="similarity-score {similarity_class}" title="Text similarity between old and new names">{similarity_pct}% match</span></div>'
                                    
                                    rename_info += '</div>'
                                
                                table_html += f'<tr class="section-row {row.get("rename_history") and "has-renames" or ""}">'
                                table_html += f'<td style="text-align: left;" class="section-name-cell">'
                                table_html += f'<div class="section-name">{row["section"]}'
                                
                                # Add a small icon to indicate renames
                                if row.get('rename_history') and len(row.get('rename_history', [])) > 0:
                                    table_html += f' <span class="rename-indicator" title="This section was renamed">↺</span>'
                                
                                table_html += '</div>'
                                table_html += rename_info
                                table_html += '</td>'
                                
                                table_html += f'<td style="text-align: left; font-family: monospace;">{row["level"]}</td>'
                                
                                for year in years:
                                    edit_count = row['edits'].get(year, None)
                                    first_year = row['lifespan'].split('-')[0]  # Extract first year from lifespan
                                    
                                    # Check if the section exists in this year
                                    section_exists = True
                                    if year < first_year:
                                        section_exists = False
                                    
                                    # Check if this section was removed in a specific year
                                    # Look for year in TOC history where this section doesn't exist
                                    if toc_history and year in toc_history:
                                        current_year_data = toc_history[year]
                                        section_titles = {s["title"].lower() for s in current_year_data["sections"]}
                                        
                                        # If section doesn't exist in this year's TOC and it's after first appearance
                                        if row['section'].lower() not in section_titles and year > first_year:
                                            section_exists = False
                                    
                                    if not section_exists:
                                        display_value = "N/A"
                                        bg_color = "#f3f4f6"  # Light gray for non-existent
                                    else:
                                        edit_count = edit_count or 0  # Convert None to 0 for existing sections
                                        display_value = str(edit_count)
                                        bg_color = get_color(edit_count)
                                    
                                    table_html += f'<td><div class="edit-cell" style="background-color: {bg_color}">{display_value}</div></td>'
                                
                                table_html += f'<td style="text-align: left;">{row["lifespan"]}</td>'
                                table_html += f'<td style="text-align: center; font-weight: 500;">{row["totalEdits"]}</td></tr>'
                                
                            
                            table_html += """
                                    </tbody>
                                </table>
                                </div>
                            """
                            
                            st.markdown(table_html, unsafe_allow_html=True)
                    
                    elif view_mode == "Section Count":
                        # Prepare CSV data
                        csv_data = []
                        for year, content in sorted(toc_history.items()):
                            level_counts = {}
                            for section in content["sections"]:
                                level = section["level"]
                                level_counts[f"Level {level}"] = level_counts.get(f"Level {level}", 0) + 1
                            row = {"Year": year}
                            row.update(level_counts)
                            csv_data.append(row)
                        
                        csv_df = pd.DataFrame(csv_data)
                        
                        col1, col2 = st.columns([6, 1])
                        with col2:
                            st.download_button(
                                "↓",
                                data=csv_df.to_csv(index=False),
                                file_name="section_counts.csv",
                                mime="text/csv",
                                help="Download data as CSV"
                            )
                        
                        fig = create_section_count_chart(toc_history)
                        st.plotly_chart(fig, use_container_width=True)
                
                else:
                    st.warning("No historical versions found.")
            else:
                st.error("Could not retrieve page content.")

    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.info("Please check if the Wikipedia page title is correct and try again.")
