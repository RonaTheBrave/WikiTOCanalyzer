import requests
from datetime import datetime
from bs4 import BeautifulSoup
import mwparserfromhell

def get_page_history(title, start_date, end_date):
    """
    Fetch revision history for a Wikipedia page between given dates.
    
    Args:
        title (str): The Wikipedia page title
        start_date (datetime.date): Start date for history
        end_date (datetime.date): End date for history
        
    Returns:
        list: List of revision data
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
        "titles": title,
        "rvprop": "ids|timestamp|content",
        "rvstart": end,
        "rvend": start,
        "rvlimit": "max"
    }
    
    revisions = []
    continue_token = None
    
    while True:
        if continue_token:
            params["rvcontinue"] = continue_token
            
        response = requests.get(api_url, params=params)
        data = response.json()
        
        # Extract page data
        pages = data["query"]["pages"]
        page_id = list(pages.keys())[0]
        
        if "revisions" in pages[page_id]:
            revisions.extend(pages[page_id]["revisions"])
        
        # Check if there are more revisions to fetch
        if "continue" in data:
            continue_token = data["continue"]["rvcontinue"]
        else:
            break
    
    return revisions

def extract_toc(wikitext):
    """
    Extract table of contents from Wikipedia page content.
    
    Args:
        wikitext (str): Wikipedia page content in wikitext format
        
    Returns:
        list: List of section data
    """
    parsed = mwparserfromhell.parse(wikitext)
    sections = []
    current_level = 1
    
    for section in parsed.get_sections(include_lead=False, flat=True):
        heading = section.filter_headings()[0]
        title = str(heading.title.strip())
        level = heading.level
        
        sections.append({
            "title": title,
            "level": level
        })
        
    return sections

def get_toc_history(title, start_date, end_date):
    """
    Get table of contents history for a Wikipedia page.
    
    Args:
        title (str): The Wikipedia page title
        start_date (datetime.date): Start date for history
        end_date (datetime.date): End date for history
        
    Returns:
        dict: Dictionary of TOC data by year
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