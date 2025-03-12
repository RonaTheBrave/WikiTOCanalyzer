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
    
    # Enhanced case detection - more explicit approach
    case_renames = {}
    # First explicitly check for case-insensitive matches (clearer debugging)
    for old_title in prev_titles - exact_matches:
        for new_title in curr_titles - exact_matches:
            if old_title.lower() == new_title.lower() and old_title != new_title:
                case_renames[new_title] = old_title
                print(f"DEBUG: Case-different rename detected: '{old_title}' → '{new_title}'")
    
    # Fall back to previous approach as well
    prev_case_map = {s.lower(): s for s in prev_titles - exact_matches - set(case_renames.values())}
    curr_case_map = {s.lower(): s for s in curr_titles - exact_matches - set(case_renames.keys())}
    
    # Find any additional sections that differ only in case
    for s_lower in set(prev_case_map.keys()) & set(curr_case_map.keys()):
        if prev_case_map[s_lower] != curr_case_map[s_lower]:
            new_title = curr_case_map[s_lower]
            old_title = prev_case_map[s_lower]
            case_renames[new_title] = old_title
            print(f"DEBUG: Additional case rename: '{old_title}' → '{new_title}'")
    
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

def calculate_toc_change_significance(current_sections, previous_sections):
    """
    Calculate the significance of changes between two TOC versions.
    Returns a significance score and change summary.
    """
    # Handle None or empty inputs
    if previous_sections is None:
        return 10, "Initial version"
    
    if not current_sections or not isinstance(current_sections, list):
        return 5, "Invalid current sections data"
        
    if not previous_sections or not isinstance(previous_sections, list):
        return 5, "Invalid previous sections data"
    
    try:
        # Safely extract titles using .get() to avoid KeyError
        current_set = {s.get("title", "") for s in current_sections if isinstance(s, dict) and "title" in s}
        previous_set = {s.get("title", "") for s in previous_sections if isinstance(s, dict) and "title" in s}
        
        # Skip empty sets
        if not current_set or not previous_set:
            return 5, "Empty section data"
        
        # Calculate changes
        added = current_set - previous_set
        removed = previous_set - current_set
        total_changes = len(added) + len(removed)
        
        # Check for hierarchy changes (level changes)
        hierarchy_changes = 0
        common_sections = current_set.intersection(previous_set)
        
        # Create lookup dictionaries
        current_lookup = {s.get("title", ""): s.get("level", 0) for s in current_sections if isinstance(s, dict) and "title" in s}
        previous_lookup = {s.get("title", ""): s.get("level", 0) for s in previous_sections if isinstance(s, dict) and "title" in s}
        
        for section in common_sections:
            if section in current_lookup and section in previous_lookup:
                if current_lookup[section] != previous_lookup[section]:
                    hierarchy_changes += 1
        
        # Calculate significance score (scale of 1-10)
        # More weight to removed sections as they're often more significant
        significance = min(10, (total_changes * 2 + hierarchy_changes * 3) / 2)
        
        # Create change summary
        summary = []
        if added:
            summary.append(f"Added {len(added)} section(s)")
        if removed:
            summary.append(f"Removed {len(removed)} section(s)")
        if hierarchy_changes:
            summary.append(f"Changed level of {hierarchy_changes} section(s)")
        
        change_summary = ", ".join(summary) if summary else "Minor changes"
        
        return significance, change_summary
    except Exception as e:
        # Add this except block to handle any errors
        return 5, f"Error calculating significance: {str(e)}"

def process_revision_history(title, mode="yearly", significance_threshold=5, start_year=2010, end_year=None):
    """
    Process revision history and extract TOC
    
    Parameters:
    - title: Wikipedia page title
    - mode: "yearly" for one revision per year, "significant" for significant changes
    - significance_threshold: threshold for significant changes (1-10 scale)
    - start_year: filter revisions from this year onwards (inclusive)
    - end_year: filter revisions up to this year (inclusive), None means current year
    """
    revisions = get_page_history(title)
    
    # Handle end_year=None by setting it to current year
    if end_year is None:
        end_year = datetime.now().year
    
    # Dictionary to store revisions by key (year or revision id)
    toc_revisions = {}
    years_processed = set()
    previous_sections = None
    prev_sections_data = None
    
    # Track all significant revisions with timestamps
    significant_revisions = []
    
    for rev in reversed(revisions):
        timestamp = rev['timestamp']
        date = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
        year = date.year
        revision_id = rev['revid']
        
        # Filter by year range
        if year < start_year or year > end_year:
            continue
            
        # For yearly mode, skip if we already have this year
        if mode == "yearly" and year in years_processed:
            continue
            
        # Get content and extract TOC
        content = get_revision_content(title, revision_id)
        if not content:
            continue
            
        sections = extract_toc(content)
        current_sections = {s["title"] for s in sections}
        
        # Calculate significance for this change
        significance, change_summary = calculate_toc_change_significance(sections, prev_sections_data)
        
        # Decide whether to include this revision
        include_revision = False
        
        if mode == "yearly":
            # Include if this is the first revision for the year
            if year not in years_processed:
                include_revision = True
                years_processed.add(year)
                revision_key = str(year)
        else:  # significant mode
            # Include if this is a significant change or first revision
            if previous_sections is None or significance >= significance_threshold:
                include_revision = True
                # Use timestamp as key for significant revisions
                formatted_date = date.strftime("%Y-%m-%d")
                revision_key = formatted_date
                significant_revisions.append({
                    "date": formatted_date,
                    "significance": significance,
                    "summary": change_summary,
                    "revid": revision_id
                })
        
        if include_revision:
            # Process the TOC data
            renamed_sections = {}
            removed_sections = set()
            
            if previous_sections is not None:
                renamed_sections = detect_renamed_sections(previous_sections, current_sections)
                removed_sections = previous_sections - current_sections - set(renamed_sections.values())
            
            # Mark sections as new or renamed
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
                "renamed": renamed_sections,
                "timestamp": timestamp,
                "revid": revision_id,
                "significance": significance,
                "change_summary": change_summary
            }
            
            toc_revisions[revision_key] = data
            
            # Update previous sections for the next iteration
            previous_sections = current_sections
            prev_sections_data = sections
    
    # For significant mode, also include metadata about all significant revisions
    if mode == "significant":
        toc_revisions["_metadata"] = {
            "significant_revisions": significant_revisions
        }
    
    return toc_revisions
    
def create_section_count_chart(toc_history):
    """
    Create section count visualization with level breakdown
    """
    data = []
    for year, content in sorted(toc_history.items()):
        if year != "_metadata" and "sections" in content:
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

    # Build rename history from toc_history if provided - with detailed debug
    if toc_history:
        print("Building rename history from TOC data")
        rename_found = False
        
        # Debug the toc_history structure
        print(f"TOC history contains {len(toc_history)} years")
        for year, data in sorted(toc_history.items()):
            has_renamed = "renamed" in data and len(data["renamed"]) > 0
            print(f"Year {year}: Has 'renamed' key: {'renamed' in data}, Has renames: {has_renamed}")
            if has_renamed:
                print(f"  Found {len(data['renamed'])} renames in year {year}")
                rename_found = True
        
        if not rename_found:
            print("WARNING: No renames found in TOC history")
            
        # Now try to build the rename history
        for year, data in sorted(toc_history.items()):
            if "renamed" in data and data["renamed"]:
                for new_name, old_name in data["renamed"].items():
                    print(f"Processing rename: '{old_name}' → '{new_name}' from year {year}")
                    
                    # Check if the keys are properly accessible
                    new_key = new_name.lower()
                    print(f"  Using lowercase new key: '{new_key}'")
                    
                    if new_key not in rename_history:
                        rename_history[new_key] = []
                        print(f"  Created new rename history entry for '{new_key}'")
                    
                    rename_history[new_key].append((old_name, year))
                    print(f"  Added rename: '{old_name}' → '{new_name}' for year {year}")

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
                    has_rename = section_key in rename_history and len(rename_history[section_key]) > 0
                    section_edits[section_key] = {
                        "section": section_title,  # Use original capitalization
                        "level": level,
                        "edits": {},
                        "totalEdits": 0,
                        "first_seen": year_str,
                        "rename_history": rename_history.get(section_key, []),
                        "has_rename": has_rename
                    }
                    section_first_seen[section_key] = year_str
                    
                    # Debug output for sections with rename history
                    if has_rename:
                        print(f"Section '{section_title}' has rename history: {rename_history[section_key]}")
                else:
                    # Update the capitalization to the most recent one
                    section_edits[section_key]["section"] = section_title
                    
                    # Make sure rename history is set even for existing sections
                    if section_key in rename_history and len(rename_history[section_key]) > 0:
                        section_edits[section_key]["rename_history"] = rename_history[section_key]
                        section_edits[section_key]["has_rename"] = True
                
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

def get_revision_url(title, revision_id):
    """
    Generate a URL to a specific Wikipedia revision
    
    Parameters:
    - title: Wikipedia page title
    - revision_id: Revision ID
    
    Returns:
    - URL to the revision
    """
    # Replace spaces with underscores for the URL
    title_formatted = title.replace(" ", "_")
    
    # Create the URL
    url = f"https://en.wikipedia.org/w/index.php?title={title_formatted}&oldid={revision_id}"
    
    return url

# Set up Streamlit page
st.set_page_config(page_title="Wikipedia TOC History Viewer", layout="wide")

st.title("Wikipedia Table of Contents History Viewer")
st.write("This tool shows how the table of contents structure has evolved over time")

with st.sidebar:
    st.header("Settings")
    wiki_page = st.text_input(
        "Enter Wikipedia Page Title",
        "Opioid-induced hyperalgesia",
        help="Enter the exact title as it appears in the Wikipedia URL"
    )
    
    # Year range selector
    st.subheader("Time Range")
    
    # Set default min and max years
    min_year_default = 2010
    max_year_default = datetime.now().year
    
    # Create year range selection with min and max sliders
    col1, col2 = st.columns(2)
    with col1:
        start_year = st.number_input("Start Year", 
                                    min_value=1990, 
                                    max_value=max_year_default,
                                    value=min_year_default,
                                    step=1)
    with col2:
        end_year = st.number_input("End Year", 
                                   min_value=1990, 
                                   max_value=max_year_default + 1,
                                   value=max_year_default,
                                   step=1)
    
    # Ensure start_year <= end_year
    if start_year > end_year:
        st.warning("Start year cannot be after end year. Adjusting end year.")
        end_year = start_year
    
    # First define the view mode
    view_mode = st.radio(
        "Analysis Mode",
        ["Timeline View", "Edit Activity", "Section Count"],
        key="view_mode"
    )
    
    # Only show TOC Version Selection for Timeline View
    if view_mode == "Timeline View":
        st.subheader("TOC Version Selection")
        toc_version_mode = st.radio(
            "Show TOC versions:",
            ["Yearly Snapshots", "Significant Changes"],
            key="toc_version_mode",
            help="Choose how TOC versions are selected. Yearly shows one version per year, Significant shows versions where important changes occurred."
        )
        
        # Add significance threshold if "Significant Changes" is selected
        if toc_version_mode == "Significant Changes":
            significance_threshold = st.slider(
                "Significance Threshold", 
                min_value=1, 
                max_value=10, 
                value=5,
                help="Controls which TOC changes appear. Higher values (8-10): major reorganizations only. " +
                    "Medium values (4-7): notable section changes. Lower values (1-3): includes minor changes " +
                    "like capitalization. Based on added, removed, renamed sections and hierarchy changes."
            )
    else:
        # Set default value for other tabs
        if "toc_version_mode" not in st.session_state:
            st.session_state.toc_version_mode = "Yearly Snapshots"
        
        # Create a hidden variable to prevent errors
        if "significance_threshold" not in st.session_state:
            st.session_state.significance_threshold = 5
    
    st.subheader("Display Options")
    show_renames = st.toggle("Enable Rename Detection", True,
                           help="When enabled, detects and highlights sections that were renamed")
    
    # Store in session state to ensure it's available throughout the app
    st.session_state['show_renames'] = show_renames
    print(f"DEBUG: Set show_renames in session state to {show_renames}")
    
    # Debug toggle value
    print(f"DEBUG: Show renames toggle is set to: {show_renames}")
    
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

if wiki_page:
    try:
        with st.spinner("Analyzing page history..."):
            current_content = get_revision_content(wiki_page)
            if current_content:
                st.success("Successfully retrieved current version")
                current_sections = extract_toc(current_content)
                
                toc_mode = "yearly" if st.session_state.toc_version_mode == "Yearly Snapshots" else "significant"
                significance_value = significance_threshold if toc_mode == "significant" else 5
                
                toc_history = process_revision_history(
                    wiki_page, 
                    mode=toc_mode,
                    significance_threshold=significance_value,
                    start_year=start_year,
                    end_year=end_year
                )
                
                if toc_history:
                    years_count = len([k for k in toc_history.keys() if k != "_metadata"])
                    if years_count > 0:
                        st.success(f"Found {years_count} historical versions from {start_year} to {end_year}")
                    else:
                        st.warning(f"No historical versions found in the selected time range ({start_year} - {end_year}). Try expanding your time range.")
                    
                    rename_summary = []
                    for year, data in sorted(toc_history.items()):
                        if year != "_metadata" and data.get("renamed"):
                            for new_name, old_name in data["renamed"].items():
                                rename_summary.append(f"{year}: '{old_name}' → '{new_name}'")
                    rename_summary = []
                    for year, data in sorted(toc_history.items()):
                        if year != "_metadata" and data.get("renamed"):
                            for new_name, old_name in data["renamed"].items():
                                rename_summary.append(f"{year}: '{old_name}' → '{new_name}'")
                    
                    if rename_summary:
                        with st.expander("Section Renames Detected"):
                            for rename in rename_summary:
                                st.write(rename)
                    
                    # Debug TOC data structure
                    with st.expander("DEBUG: TOC Rename Data"):
                        st.write("Checking TOC history structure")
                        rename_found = False
                        for year, data in sorted(toc_history.items()):
                            if year != "_metadata" and "renamed" in data and data["renamed"]:
                                rename_found = True
                                st.write(f"Year {year} has {len(data['renamed'])} renames in TOC history")
                                # Display first 3 renames
                                for i, (new_name, old_name) in enumerate(list(data["renamed"].items())[:3]):
                                    st.write(f"  - '{old_name}' → '{new_name}'")
                        
                        if not rename_found:
                            st.write("No renames found in any year in TOC history")
                            
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
                                if year != "_metadata" and isinstance(data, dict) and "sections" in data:
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
                                <div style="display: flex; align-items: center; gap: 0.5rem;">
                                    <div style="display: flex; color: #9333ea; letter-spacing: -1px;">
                                        <span>●●●●●</span>
                                    </div>
                                    <span>Significance rating (1-5)</span>
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

                            /* Level indicator styles */
                            .level-line {
                                position: absolute;
                                left: 0;
                                top: 50%;
                                transform: translateY(-50%);
                                width: 3px;
                                border-radius: 3px;
                                height: 18px; /* Fixed height for all indicators */
                            }
                            
                            .section-title {
                                display: inline-block;
                                vertical-align: middle; /* Align text vertically */
                                line-height: 1.2; /* Improve text line height */
                                padding: 2px 4px;
                                border-radius: 4px;
                                max-width: 100%;
                                box-sizing: border-box;
                            }
                            
                            .section-container {
                                position: relative;
                                padding: 6px 4px 6px 24px; /* Increased vertical padding */
                                margin: 2px 0;
                                overflow: hidden;
                                width: 100%;
                                box-sizing: border-box;
                                display: flex;
                                align-items: center; /* Center align content vertically */
                            }
                            .level-1-line { background-color: #3b82f6; left: 4px; }
                            .level-2-line { background-color: #60a5fa; left: 8px; }
                            .level-3-line { background-color: #93c5fd; left: 12px; }
                            .level-4-line { background-color: #bfdbfe; left: 16px; }
                            .level-5-line { background-color: #dbeafe; left: 20px; }
                            
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
                            .significance-indicator {
                                display: inline-block;
                                margin-left: 4px;
                                color: #9333ea;
                            }
                            .change-summary {
                                color: #4b5563;
                                white-space: normal;
                                overflow: hidden;
                                text-overflow: ellipsis;
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
                        

                        def format_display_date(key):
                            """Format display date for timeline view"""
                            try:
                                if "-" in key and len(key) == 10:  # Looks like a date YYYY-MM-DD
                                    date_obj = datetime.strptime(key, "%Y-%m-%d")
                                    return date_obj.strftime("%b %d, %Y")
                                return key  # Return as is if not a date
                            except:
                                return key  # Return as is on any error
                                
                        # Display timeline columns
                        # Skip metadata entry if present and ensure each item has sections
                        display_items = {k: v for k, v in toc_history.items() 
                                        if k != "_metadata" and isinstance(v, dict) and "sections" in v}
                        
                        if not display_items:
                            st.warning("No TOC versions found with the current settings. Try adjusting the significance threshold.")
                        else:
                            cols = st.columns(len(display_items))
                            for idx, (key, data) in enumerate(sorted(display_items.items())):
                                with cols[idx]:
                                    # Show revision date and change summary for significant mode
                                    if st.session_state.toc_version_mode == "Significant Changes":
                                        display_date = format_display_date(key)  # Format date if it's a date
                                        significance_value = data.get("significance", 0)
                                        # Calculate how many dots should be filled (out of 5)
                                        filled_dots = max(1, min(5, round(significance_value/2)))
                                        # Create string of filled and unfilled dots
                                        significance_indicator = "●" * filled_dots + "<span style='opacity: 0.3;'>●</span>" * (5 - filled_dots)
                                        
                                        header_html = f'''
                                        <div class="year-header">
                                            <a href="{get_revision_url(wiki_page, data["revid"])}" target="_blank" style="text-decoration: none; color: inherit;">
                                                {display_date} <span style="font-size: 0.7em; color: #6b7280;">↗</span>
                                            </a>
                                            <div class="significance-indicator" title="Significance: {significance_value}/10">
                                                <span style="color: #9333ea; letter-spacing: -1px;">{significance_indicator}</span>
                                            </div>
                                            <div class="change-summary" style="font-size: 0.8em; font-weight: normal; margin-top: 4px;">
                                                {data.get('change_summary', '')}
                                            </div>
                                        </div>
                                        '''
                                        
                                        st.markdown(header_html, unsafe_allow_html=True)
                                    else:
                                        # Original yearly view
                                        # Add hyperlink to year header
                                        st.markdown(f'<div class="year-header"><a href="{get_revision_url(wiki_page, data["revid"])}" target="_blank" style="text-decoration: none; color: inherit;">{key} <span style="font-size: 0.7em; color: #6b7280;">↗</span></a></div>', unsafe_allow_html=True)
                                        
                                    # Display sections
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
                                                    {"".join([f'<div class="level-line level-{i}-line"></div>' for i in range(1, section["level"]+1)])}
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
                                                    {"".join([f'<div class="level-line level-{i}-line"></div>' for i in range(1, section["level"]+1)])}
                                                    {indent}<span class="section-title {class_str}">
                                                        {section["title"]}
                                                    </span>
                                                </div>
                                            """, unsafe_allow_html=True)
                                    
                                    # Display removed sections
                                    if "removed" in data:
                                        for removed_section in data["removed"]:
                                            st.markdown(f"""
                                                <div class="section-container">
                                                    <div class="level-line level-1-line" style="background-color: #ef4444;"></div>
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


                        # Show current rename detection status
                        st.info(f"Rename detection is currently {'ENABLED' if st.session_state.get('show_renames', True) else 'DISABLED'}")
                        
                        # Get real edit activity data
                        revisions = get_page_history(wiki_page)
                        st.write("Calculating edit activity...")

                        # Debugging section
                        with st.expander("Debug Rename Information"):
                            st.write("Checking for rename data in TOC history...")
                            rename_count = 0
                            for year, data in sorted(toc_history.items()):
                                if year != "_metadata" and data.get("renamed"):
                                    st.write(f"Year {year}: {len(data['renamed'])} renames found")
                                    rename_count += len(data['renamed'])
                                    
                                    # Show some details
                                    for new_name, old_name in list(data['renamed'].items())[:5]:  # Show only first 5
                                        st.write(f"  '{old_name}' → '{new_name}'")
                            
                            st.write(f"Total renames detected: {rename_count}")
                            
                        edit_data = calculate_edit_activity(revisions, wiki_page, toc_history)
                        
                        # Debug: Check for rename history in edit_data
                        with st.expander("DEBUG: Edit Data Rename Info"):
                            st.write("Examining edit_data for rename history")
                            sections_with_rename = [row for row in edit_data if row.get('rename_history') and len(row.get('rename_history', [])) > 0]
                            st.write(f"Found {len(sections_with_rename)} sections with rename history in edit_data")
                            
                            if sections_with_rename:
                                st.write("First few sections with rename history:")
                                for i, row in enumerate(sections_with_rename[:3]):
                                    st.write(f"  - Section '{row['section']}' has {len(row['rename_history'])} renames:")
                                    for old_name, year in row['rename_history']:
                                        st.write(f"    * In {year}: '{old_name}' → '{row['section']}'")
                            else:
                                st.write("No sections with rename history found in edit_data")
                        
                        if not edit_data:
                            st.warning("No edit activity data found.")
                        else:
                            # Get all years from the data
                            all_years = set()
                            for item in edit_data:
                                all_years.update(item["edits"].keys())
                                
                            # Get the full range of years (fill in any missing years)
                            if all_years:
                                min_year = min(int(year) for year in all_years)
                                max_year = max(int(year) for year in all_years)
                                # Ensure all years in the range are included
                                all_years = set(str(year) for year in range(min_year, max_year + 1))
                                
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
                                    .edit-table-container {
                                        position: relative;
                                        overflow: auto;
                                        max-height: 80vh;
                                        max-width: 100%;
                                    }
                                    .edit-table {
                                        width: 100%;
                                        border-collapse: separate;
                                        border-spacing: 0;
                                    }
                                    .edit-table th, .edit-table td {
                                        padding: 8px;
                                        text-align: center;
                                        border: 1px solid #e5e7eb;
                                        min-width: 80px;
                                    }
                                    .edit-table th {
                                        background-color: #f9fafb;
                                        font-weight: 500;
                                        position: sticky;
                                        top: 0;
                                        z-index: 10;
                                    }
                                    .edit-table th:first-child {
                                        left: 0;
                                        z-index: 20;
                                    }
                                    .edit-table td:first-child {
                                        position: sticky;
                                        background-color: #ffffff;
                                        z-index: 5;
                                        text-align: left;
                                        left: 0;
                                        max-width: 200px;
                                        overflow: hidden;
                                        text-overflow: ellipsis;
                                        white-space: nowrap;
                                    }
                                    .edit-table tr:nth-child(odd) td:first-child {
                                        background-color: #f9fafb;
                                    }
                                    .edit-cell {
                                        border-radius: 4px;
                                        padding: 4px 8px;
                                        white-space: nowrap;
                                    }
                                </style>
                            """, unsafe_allow_html=True)
                            # Add CSS for the year links
                            st.markdown("""
                            <style>
                                .year-link {
                                    text-decoration: none;
                                    color: inherit;
                                    display: block;
                                }
                                .year-link:hover {
                                    color: #2563eb;
                                }
                                .external-icon {
                                    font-size: 0.7em;
                                    color: #6b7280;
                                    margin-left: 2px;
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
                                    /* Simplified rename styling */
                                    .renamed-section {
                                        background-color: #fcf6ff;
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
                                <div class="edit-table-container">
                                <table class="edit-table">
                                    <thead>
                                        <tr>
                                            <th style="text-align: left;">Section</th>
                                            <th style="text-align: left;">Level</th>
                            """
                            
                            # Add year columns with links to revisions
                            for year in years:
                                # Find the revision ID for this year
                                revision_id = None
                                if year in toc_history:
                                    revision_id = toc_history[year].get("revid")
                                
                                if revision_id:
                                    table_html += f'<th><a href="{get_revision_url(wiki_page, revision_id)}" target="_blank" class="year-link">{year}<span class="external-icon">↗</span></a></th>'
                                else:
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
                                
                                # Simple rename indicator without complex history
                                rename_info = ""
                                has_rename = row.get('rename_history') and len(row.get('rename_history', [])) > 0
                                
                                # Simplified row with clear cell background for renamed sections
                                table_html += f'<tr class="section-row">'
                                
                                # Simple background color for renamed sections
                                cell_bg = "#fcf6ff" if has_rename else ""
                                cell_style = f'background-color: {cell_bg};' if has_rename else ""
                                
                                table_html += f'<td style="text-align: left; {cell_style}">'
                                
                                # Make renamed sections stand out with a badge
                                if has_rename:
                                    old_name = row['rename_history'][0][0]  # Get first old name
                                    year = row['rename_history'][0][1]      # Get year of first rename
                                    table_html += f'<div style="padding: 4px;">'
                                    table_html += f'<strong>{row["section"]}</strong> '
                                    table_html += f'<span style="display: inline-block; background-color: #e9d5ff; color: #6b21a8; font-weight: bold; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; margin-left: 4px;">renamed</span>'
                                    table_html += f'<div style="font-size: 0.8rem; color: #6b21a8; margin-top: 2px;">Previously: {old_name} ({year})</div>'
                                    table_html += f'</div>'
                                else:
                                    table_html += f'{row["section"]}'
                                
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
                            if year != "_metadata" and "sections" in content:
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
