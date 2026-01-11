# GialloZafferano Scraper

A Python-based incremental scraper for [GialloZafferano.it](https://www.giallozafferano.it), designed to build a dataset of Italian recipes with ingredients and instructions.

## Features

- **Incremental Scraping**: Checks the database before scraping to avoid duplicates.
- **RAG-Optimized**: Instructions are condensed into single paragraphs for easier embedding/retrieval.
- **Structured Data**: Ingredients are parsed into structured groups/items.
- **Polite**: Includes delays to respect the target server.

## Prerequisites

- Python 3.8+
- **MongoDB Server**: You must have the MongoDB Database Server installed and running locally on the default port (27017).
  - [Download MongoDB Community Server](https://www.mongodb.com/try/download/community)
  - *Note: Installing `pymongo` via pip only installs the Python driver, not the database server itself.*

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/alfiobonanno/giallozafferano-scraper.git
   cd giallozafferano-scraper
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # Windows
   .\venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

3. Install dependencies:
   
   > [!NOTE]
   > Please review `requirements.txt` and modify it if you have specific version requirements or additional dependencies.
   
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Ensure MongoDB is running.
2. Run the scraper:
   ```bash
   python giallozafferano_scraper.py
   ```

The script will start scraping from the `ricette-cat` page and populate the `recipes_new` database in the `italian_giallozafferano` collection.

## Data Structure

Each recipe document contains:
- `title`: Recipe name
- `url`: Source URL
- `description`: Brief description
- `ingredients`: List of ingredient groups (e.g., "Impasto", "Ripieno")
- `instructions`: Full preparation steps as text
- `metadata`: Prep time, calories, difficulty

> [!TIP]
> See `recipes_full.json` for a complete example of the extracted data structure.

## Automated Updates

You can schedule this script to run automatically (e.g., via **Cron** on Linux or **Task Scheduler** on Windows) to keep your database up-to-date.

The scraper is designed to be **incremental**: it checks each recipe URL against the database and **stops immediately** when it finds a match. This makes repeated runs efficient.

To target only the *newest* recipes, update the `main()` function in `giallozafferano_scraper.py` to start from the "Latest Recipes" page:

```python
def main():
    base_domain = "https://www.giallozafferano.it"
    # CHANGE THIS: Point to the 'Latest Recipes' page
    current_url = urljoin(base_domain, "ricette-cat//")
    
    # TO THIS:
    
    current_url = urljoin(base_domain, "Ultime-ricette/")
    # ... rest of the script
```

With this change, the script will scan the latest additions and exit as soon as it encounters a recipe you've already scraped.

## Disclaimer

> [!CAUTION]
> **Terms of Use & API Restrictions**
>
> This scraper is intended strictly for **academic purposes**, learning web scraping techniques (in particular, Scrapling exceptional stealth capabilities), and practicing with MongoDB. 
> 
> Consistent with [GialloZafferano's Terms and Conditions](https://www.giallozafferano.it/), this tool must **NOT** be used for financial gain, commercial purposes, or mass redistribution of their content. Always respect the website's `robots.txt` and rate limits.
>
> **Maintenance Status**
> This script is verified to work as of **11/01/2026**. Please note that web scrapers are inherently fragile; future changes to GialloZafferano's HTML structure or CSS class names may cause the scraper to fail, requiring updates to the selectors.
