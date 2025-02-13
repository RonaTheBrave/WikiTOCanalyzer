import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import requests
import mwparserfromhell
from urllib.parse import quote

def get_page_history(title):
    """
    Fetch revision history for a Wikipedia page from last 5 years
    """
    # Calculate dates - going back from 2024 instead of using future dates
    end_date = "20240213"  # Fixed current date in 2024
    start_date = "20190213"  # 5 years back
    
    api_url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "prop": "revisions",
        "titles": title,
        "rvprop": "content|timestamp",
        "rvstart": end_date,
        "rvend": start_date,
        "rvlimit": "20",  # Increased limit
        "rvslots": "main",
        "formatversion": "2"
    }
    
    st.write("Making API request for date range:", start_date, "to", end_date)
    
    try:
        response = requests.get(api_url, params=params)
        data = response.json()
        st.write("API Response Status:", response.status_code)
        
        if 'query' in data and 'pages' in data['query']:
            pages = data['query']['pages']
            if pages and len(pages) > 0:
                page = pages[0]
                if 'revisions' in page:
                    revs = page['revisions']
                    st.write(f"Successfully retrieved {len(revs)} revisions")
                    if revs:
                        # Show sample of first revision content
                        first_rev = revs[0]
                        if 'slots' in first_rev and 'main' in first_rev['slots']:
                            content = first_rev['slots']['main']['content']
                            st.write("Sample of first revision content:", content[:200])
                    return revs
                else:
                    st.write("Page found but no revisions in response:", page)
            else:
                st.write("No pages found in response")
        else:
            st.write("Unexpected API response:", data)
            
    except Exception as e:
        st.error(f"Error in API request: {str(e)}")
    
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
                    st.write(f"Found section: {title} (level {level})")
    except Exception as e:
        st.error(f"Error extracting sections: {str(e)}")
    
    if sections:
        st.write(f"Successfully extracted {len(sections)} sections")
    return sections

def get_toc_history(title):
    """
    Get table of contents history for a Wikipedia page.
    """
    revisions = get_page_history(title)
    toc_history = {}
    
    for rev in revisions:
        try:
            year = datetime.strptime(rev["timestamp"], "%Y-%m-%dT%H:%M:%SZ").year
            
            # Get content from revision
            content = None
            if 'slots' in rev and 'main' in rev['slots']:
                content = rev['slots']['main']['content']
            
            if content:
                sections = extract_toc(content)
                if sections:
                    # Only store first occurrence for each year
                    if str(year) not in toc_history:
                        toc_history[str(year)] = sections
                        st.write(f"Added sections for year {year}")
                        
        except Exception as e:
            st.error(f"Error processing revision: {str(e)}")
            continue
    
    return dict(sorted(toc_history.items()))

# Set up Streamlit page
st.set_page_config(page_title="Wikipedia TOC History Viewer", layout="wide")

st.title("Wikipedia TOC History Viewer")
st.write("This tool shows the evolution of Wikipedia article table of contents over the past 5 years (2019-2024)")

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
        with st.spinner("Fetching page history..."):
            toc_history = get_toc_history(wiki_page)
            
            if not toc_history:
                st.warning("No table of contents history found for this page.")
            else:
                st.success(f"Found table of contents history spanning {len(toc_history)} years")
                
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
                                st.markdown(
                                    f"{indent}{section['title']} "
                                    f"<span style='color:gray'>{'*' * section['level']}</span>",
                                    unsafe_allow_html=True
                                )
                            st.markdown("---")
                
                with tab2:
                    # Convert data for heatmap
                    edit_data = []
                    for date, sections in toc_history.items():
                        year = int(date)
                        for section in sections:
                            edit_data.append({
                                'Year': year,
                                'Section': section['title'],
                                'Level': section['level']
                            })
                    
                    df = pd.DataFrame(edit_data)
                    
                    if not df.empty:
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

    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.info("Please check if the Wikipedia page title is correct and try again.")
