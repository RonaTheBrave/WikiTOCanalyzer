import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import requests

def get_page_content(title):
    """
    Fetch current content of a Wikipedia page
    """
    api_url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "parse",
        "page": title,
        "format": "json",
        "prop": "wikitext",
        "formatversion": "2"
    }
    
    st.write("Making API request to get current page content")
    st.write("Parameters:", params)
    
    try:
        response = requests.get(api_url, params=params)
        data = response.json()
        
        st.write("Response Status:", response.status_code)
        st.write("Response Data:", data)
        
        if 'parse' in data and 'wikitext' in data['parse']:
            content = data['parse']['wikitext']
            st.write("Content length:", len(content))
            st.write("First 500 characters:", content[:500])
            return content
        else:
            st.write("Could not find content in response")
            return None
            
    except Exception as e:
        st.error(f"Error in API request: {str(e)}")
        return None

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

# Set up Streamlit page
st.set_page_config(page_title="Wikipedia TOC Viewer", layout="wide")

st.title("Wikipedia Table of Contents Viewer")
st.write("This tool shows the current table of contents structure of a Wikipedia article")

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
        with st.spinner("Fetching page content..."):
            content = get_page_content(wiki_page)
            
            if content:
                sections = extract_toc(content)
                
                if sections:
                    st.success(f"Found {len(sections)} sections")
                    
                    # Display sections
                    st.header("Table of Contents")
                    for section in sections:
                        indent = "&nbsp;" * (4 * (section['level'] - 1))
                        st.markdown(
                            f"{indent}{section['title']} "
                            f"<span style='color:gray'>{'*' * section['level']}</span>",
                            unsafe_allow_html=True
                        )
                else:
                    st.warning("No sections found in the page content.")
            else:
                st.error("Could not retrieve page content.")

    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.info("Please check if the Wikipedia page title is correct and try again.")
