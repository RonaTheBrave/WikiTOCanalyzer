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
    
    # API endpoint
    api_url = "https://en.wikipedia.org/w/api.php"
    
    # Parameters for the API request
    params = {
        "action": "query",
        "format": "json",
        "prop": "revisions",
        "titles": quote(title),
        "rvprop": "content|timestamp",
        "rvstart": end,
        "rvend": start,
        "rvlimit": "1",
        "formatversion": "2",
        "redirects": "1",
        "rvslots": "main",
        "rvdir": "newer"
    }
    
    st.write("API URL:", api_url)
    st.write("Parameters:", params)
    
    revisions = []
    continue_token = None
    
    st.write(f"Fetching revisions for '{title}' between {start} and {end}")
    
    while True:
        if continue_token:
            params["rvcontinue"] = continue_token
        
        try:
            response = requests.get(api_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            st.write("Full API Response:", data)
            
            if 'query' in data:
                if 'pages' in data['query']:
                    pages = data['query']['pages']
                    st.write("Found pages in response")
                    st.write("Page data:", pages)
                    
                    if pages and len(pages) > 0:
                        page = pages[0]  # formatversion=2 returns array
                        if 'revisions' in page:
                            for rev in page['revisions']:
                                if 'slots' in rev and 'main' in rev['slots']:
                                    content = rev['slots']['main']['content']
                                    st.write(f"Found content of length: {len(content)}")
                                    rev['content'] = content  # Store content in a standardized way
                                    revisions.append(rev)
                                elif '*' in rev:
                                    content = rev['*']
                                    st.write(f"Found content of length: {len(content)}")
                                    revisions.append(rev)
                            st.write(f"Retrieved {len(page['revisions'])} revisions")
                else:
                    st.write("No pages found in response")
            else:
                st.write("No query data in response")
            
            # Check for more results
            if 'continue' in data:
                continue_token = data['continue']['rvcontinue']
            else:
                break
                
        except Exception as e:
            st.error(f"Error fetching revisions: {str(e)}")
            break
    
    st.write(f"Total revisions retrieved: {len(revisions)}")
    return revisions

def extract_toc(wikitext):
    """
    Extract table of contents from Wikipedia page content.
    """
    sections = []
    try:
        st.write("Processing wikitext length:", len(wikitext))
        st.write("First 500 chars of wikitext:", wikitext[:500])
        
        # Simple section extraction using regex pattern
        lines = wikitext.split('\n')
        in_section = False
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            # Look for section headers of various forms
            if line.startswith('==') and line.endswith('=='):
                # Standard section header
                raw_title = line.strip('=').strip()
                level = (len(line) - len(raw_title.strip())) // 2
                if raw_title and level > 0:
                    current_section = {
                        "title": raw_title,
                        "level": level
                    }
                    sections.append(current_section)
                    st.write(f"Found section: {raw_title} (level {level})")
            
            # You could add more section pattern matching here
            
        st.write(f"Total sections found: {len(sections)}")
        
    except Exception as e:
        st.error(f"Error parsing sections: {str(e)}")
        st.write("Problematic wikitext:", wikitext[:500] + "...")
    
    return sections

def get_toc_history(title, start_date, end_date):
    """
    Get table of contents history for a Wikipedia page.
    """
    # Get revision history
    revisions = get_page_history(title, start_date, end_date)
    
    # Process revisions by year
    toc_history = {}
    processed_years = set()
    
    for rev in revisions:
        year = datetime.strptime(rev["timestamp"], "%Y-%m-%dT%H:%M:%SZ").year
        
        # Only process one revision per year
        if year not in processed_years:
            if 'content' in rev:  # New API format
                sections = extract_toc(rev["content"])
            elif '*' in rev:  # Old API format
                sections = extract_toc(rev["*"])
            else:
                continue
                
            # Mark new sections by comparing with previous year
            if toc_history:
                prev_year = max(toc_history.keys())
                prev_sections = {s["title"] for s in toc_history[prev_year]}
                for section in sections:
                    if section["title"] not in prev_sections:
                        section["isNew"] = True
            
            toc_history[str(year)] = sections
            processed_years.add(year)
    
    return dict(sorted(toc_history.items()))

# Set up Streamlit page
st.set_page_config(page_title="Wikipedia TOC History Viewer", layout="wide")

st.title("Wikipedia TOC History Viewer")

# Input section
with st.sidebar:
    st.header("Settings")
    wiki_page = st.text_input(
        "Enter Wikipedia Page Title",
        "Dog",
        help="Enter the exact title as it appears in the Wikipedia URL"
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
                    
                    # Add debug information
                    st.write("Data shape:", df.shape)
                    st.write("Data columns:", df.columns.tolist())
                    
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
                        st.warning("No data available for visualization. Try adjusting the date range or check if the Wikipedia page exists.")

    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.info("Please check if the Wikipedia page title is correct and try again.")
