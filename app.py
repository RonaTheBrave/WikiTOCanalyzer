import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import requests
import mwparserfromhell
from urllib.parse import quote

def get_page_history(title, start_date, end_date):
    """
    Fetch revision history for a Wikipedia page between given dates.
    """
    # Format dates for API
    start = start_date.strftime("%Y%m%d")
    end = end_date.strftime("%Y%m%d")
    
    # API endpoint with corrected parameters for content retrieval
    api_url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "prop": "revisions",
        "titles": title,
        "rvprop": "timestamp|user|comment|content",  # Added more properties
        "rvstart": end,
        "rvend": start,
        "rvlimit": "10",  # Increased limit
        "rvdir": "older",
        "rvslots": "*",
        "formatversion": "2"
    }
    
    st.write("Making API request with parameters:", params)
    
    revisions = []
    try:
        response = requests.get(api_url, params=params)
        data = response.json()
        
        if 'query' in data and 'pages' in data['query']:
            page = data['query']['pages'][0]  # Using formatversion=2
            if 'revisions' in page:
                st.write(f"Found {len(page['revisions'])} revisions")
                revisions = page['revisions']
                
                # Print first revision content for debugging
                if revisions:
                    first_rev = revisions[0]
                    if 'slots' in first_rev and 'main' in first_rev['slots']:
                        content = first_rev['slots']['main']['content']
                        st.write("Sample content (first 500 chars):", content[:500])
            else:
                st.write("No revisions found in the response")
                st.write("Full page data:", page)
        else:
            st.write("Unexpected API response format:", data)
            
    except Exception as e:
        st.error(f"Error making API request: {str(e)}")
    
    return revisions

def extract_toc(wikitext):
    """
    Extract table of contents from Wikipedia page content.
    """
    sections = []
    try:
        # Clean up the wikitext and split into lines
        lines = wikitext.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('==') and line.endswith('=='):
                # Count the equals signs to determine level
                left_count = 0
                for char in line:
                    if char == '=':
                        left_count += 1
                    else:
                        break
                
                title = line.strip('=').strip()
                level = left_count // 2
                
                if title and level > 0:
                    sections.append({
                        "title": title,
                        "level": level
                    })
                    st.write(f"Found section: {title} (level {level})")
    
    except Exception as e:
        st.error(f"Error extracting TOC: {str(e)}")
    
    return sections

def get_toc_history(title, start_date, end_date):
    """
    Get table of contents history for a Wikipedia page.
    """
    revisions = get_page_history(title, start_date, end_date)
    toc_history = {}
    
    for rev in revisions:
        try:
            year = datetime.strptime(rev["timestamp"], "%Y-%m-%dT%H:%M:%SZ").year
            content = None
            
            # Extract content from revision
            if 'slots' in rev and 'main' in rev['slots']:
                content = rev['slots']['main']['content']
            elif '*' in rev:
                content = rev['*']
                
            if content:
                sections = extract_toc(content)
                if sections:  # Only add if we found sections
                    if str(year) in toc_history:
                        # Compare with existing sections
                        existing_sections = {s["title"] for s in toc_history[str(year)]}
                        for section in sections:
                            if section["title"] not in existing_sections:
                                section["isNew"] = True
                    else:
                        toc_history[str(year)] = sections
                        
        except Exception as e:
            st.error(f"Error processing revision: {str(e)}")
            continue
    
    return dict(sorted(toc_history.items()))

# Set up Streamlit page
st.set_page_config(page_title="Wikipedia TOC History Viewer", layout="wide")

st.title("Wikipedia TOC History Viewer")
st.write("This tool shows how the table of contents of a Wikipedia article has evolved over time.")

# Input section
with st.sidebar:
    st.header("Settings")
    wiki_page = st.text_input(
        "Enter Wikipedia Page Title",
        "Dog",
        help="Enter the exact title as it appears in the Wikipedia URL (e.g., 'Python_(programming_language)')"
    )
    
    end_date = st.date_input(
        "End Date",
        datetime.now().date(),
        help="Select the end date for the history view"
    )
    
    years_back = st.slider(
        "Years of History",
        min_value=1,
        max_value=10,
        value=5,
        help="Select how many years of history to view"
    )
    
    start_date = end_date - timedelta(days=365*years_back)

if wiki_page:
    try:
        with st.spinner("Fetching page history..."):
            # Get TOC history
            toc_history = get_toc_history(wiki_page, start_date, end_date)
            
            if not toc_history:
                st.warning("No table of contents history found for this page and date range.")
            else:
                # Display TOC history
                st.header("Table of Contents History")
                
                # Create tabs for different views
                tab1, tab2 = st.tabs(["Timeline View", "Edit Activity"])
                
                with tab1:
                    # Display TOC timeline
                    for date, sections in toc_history.items():
                        col = st.columns([1, 3])
                        with col[0]:
                            st.write(f"**{date}**")
                        with col[1]:
                            for section in sections:
                                indent = "&nbsp;" * (4 * (section['level'] - 1))
                                status = "🆕 " if section.get('isNew') else ""
                                st.markdown(
                                    f"{indent}{status}{section['title']} "
                                    f"<span style='color:gray'>{'*' * section['level']}</span>",
                                    unsafe_allow_html=True
                                )
                            st.markdown("---")
                
                with tab2:
                    # Convert data for heatmap
                    edit_data = []
                    for date, sections in toc_history.items():
                        year = datetime.strptime(date, "%Y").year
                        for section in sections:
                            edit_data.append({
                                'Year': year,
                                'Section': section['title'],
                                'Level': section['level'],
                                'Status': 'New' if section.get('isNew') else 'Existing'
                            })
                    
                    df = pd.DataFrame(edit_data)
                    
                    if not df.empty:
                        # Create heatmap using plotly
                        fig = px.density_heatmap(
                            df,
                            x='Year',
                            y='Section',
                            title='Section Edit Activity',
                            color_continuous_scale='Reds'
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("No data available for visualization.")

    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.info("Please check if the Wikipedia page title is correct and try again.")
