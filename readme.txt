# Wikipedia TOC History Viewer

A Streamlit application that allows users to explore the evolution of Wikipedia article table of contents over time. This tool helps visualize how the structure and organization of Wikipedia articles change over the years.

## Features

- Enter any Wikipedia page title to analyze its history
- View table of contents changes over multiple years
- Interactive timeline view showing section additions and changes
- Heat map visualization of edit activity
- Customizable date range for analysis

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/wikipedia-toc-history.git
cd wikipedia-toc-history
```

2. Create a virtual environment (optional but recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Run the Streamlit app:
```bash
streamlit run app.py
```

2. Open your web browser and navigate to the URL shown in the terminal (typically http://localhost:8501)

3. Enter a Wikipedia page title and select your desired date range

4. Explore the TOC history through different visualization options

## How It Works

The application uses the Wikipedia API to:
- Fetch revision histories for specified articles
- Extract table of contents from each revision
- Track changes and additions to sections over time
- Visualize the evolution of article structure

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.