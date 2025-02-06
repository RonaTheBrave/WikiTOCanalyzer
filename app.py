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
        "rvprop": "ids|timestamp|content|user",
        "rvstart": end,
        "rvend": start,
        "rvlimit": "500",
        "rvslots": "main"
    }
    
    revisions = []
    continue_token = None
    
    st.write(f"Fetching revisions for '{title}' between {start} and {end}")
    
    while True:
        if continue_token:
            params["rvcontinue"] = continue_token
            
        response = requests.get(api_url, params=params)
        st.write("API Response Status:", response.status_code)
        data = response.json()
        st.write("API Response:", data)
        
        if 'error' in data:
            raise Exception(f"Wikipedia API error: {data['error'].get('info', 'Unknown error')}")
            
        if 'query' not in data or 'pages' not in data['query']:
            raise Exception("Unexpected API response format")
            
        # Extract page data
        pages = data["query"]["pages"]
        page_id = list(pages.keys())[0]
        
        if "revisions" in pages[page_id]:
            for rev in pages[page_id]["revisions"]:
                if "*" in rev:  # Make sure we have content
                    revisions.append(rev)
            st.write(f"Found {len(revisions)} revisions so far")
        
        # Check if there are more revisions to fetch
        if "continue" in data:
            continue_token = data["continue"]["rvcontinue"]
        else:
            break
    
    return revisions

def extract_toc(wikitext):
    """
    Extract table of contents from Wikipedia page content.
    """
    try:
        parsed = mwparserfromhell.parse(wikitext)
        sections = []
        
        # First try to get sections with the parser
        for section in parsed.get_sections(include_lead=False, flat=True):
            try:
                headings = section.filter_headings()
                if headings:
                    heading = headings[0]
                    title = str(heading.title.strip())
                    level = heading.level
                    
                    sections.append({
                        "title": title,
                        "level": level
                    })
            except Exception as e:
                st.write(f"Error processing section: {str(e)}")
                continue
        
        # If we found no sections, try a simpler approach
        if not sections:
            # Look for common section markers
            lines = wikitext.split('\n')
            for line in lines:
                if line.startswith('==') and line.endswith('=='):
                    title = line.strip('= ')
                    level = line.count('=') // 2
                    sections.append({
                        "title": title,
                        "level": level
                    })
        
        st.write(f"Found {len(sections)} sections")
        return sections
        
    except Exception as e:
        st.write(f"Error parsing wikitext: {str(e)}")
        return []

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
            sections = extract_toc(rev["*"])
            
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
        "Dog",  # Changed to a simpler example
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
