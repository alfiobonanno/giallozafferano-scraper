"""
GialloZafferano Recipe Scraper
==============================

This script scrapes Italian recipes from GialloZafferano.it.
It performs an incremental scrape:
1. Iterates through recipe category pages.
2. Extracts recipe metadata (title, URL, difficulty, prep time, etc.).
3. Checks if the recipe already exists in the local MongoDB database.
4. If new, visits the detail page to extract ingredients and instructions.
5. Saves data immediately to MongoDB to prevent data loss.

Dependencies:
- pymongo: Database interaction
- scrapling: Efficient scraping session handling
"""

import re
import json
import time
import logging
from urllib.parse import urljoin
from pymongo import MongoClient
from scrapling.fetchers import FetcherSession

# --- CONFIGURATION & LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# MongoDB Connection
client = MongoClient('mongodb://localhost:27017/')
db = client['recipes_new']
collection = db['italian_giallozafferano']

# Ensure 'url' is indexed for fast lookups during the incremental check
collection.create_index("url", unique=True)

# --- HELPER FUNCTIONS ---

def clean_data(text):
    """
    Standardizes whitespace and fixes common punctuation spacing issues.
    
    Args:
        text (str): The raw text to clean.
        
    Returns:
        str: Cleaned text or empty string if input is None.
    """
    if not text: 
        return ""
    text = " ".join(text.split())
    return text.replace(" .", ".").replace(" ,", ",")

def parse_ingredients(recipe_page):
    """
    Extracts and groups ingredients from the recipe page.
    
    Returns a list of dictionaries, where each dictionary represents a group 
    (e.g., "For the dough") and contains a list of ingredient items.
    Optimal for Mongo.
    """
    ingredients_list = []
    sections = recipe_page.css('dl.gz-list-ingredients')
    
    for section in sections:
        title_node = section.css_first('.gz-title-ingredients')
        cat_name = clean_data(title_node.text) if title_node else "Ingredienti di base"
        
        items_in_group = []
        for item in section.css('.gz-ingredient'):
            name_node = item.css_first('a')
            qty_node = item.css_first('span')
            
            items_in_group.append({
                "item": clean_data(name_node.text) if name_node else "N/A",
                "quantity": clean_data(qty_node.text) if qty_node else "q.b."
            })
        
        ingredients_list.append({
            "group": cat_name,
            "items": items_in_group
        })
    return ingredients_list

def parse_instructions(recipe_page):
    """
    Extracts recipe steps and joins them into a single continuous paragraph.
    This format is optimized for RAG (Retrieval-Augmented Generation) applications.
    """
    steps = []
    containers = recipe_page.css('div.gz-content-recipe-step')
    for container in containers:
        # Exclude step numbers to keep text clean
        fragments = container.css('*:not(.num-step)::text').get_all()
        step_text = clean_data(" ".join(fragments))
        if step_text:
            steps.append(step_text)
    
    return " ".join(steps)

def scrape_recipe_detail(session, url, title, card_meta):
    """
    Fetches and parses the full details of a single recipe.
    
    Combines scraped data with metadata from the list page into a flat structure.
    
    Args:
        session: Active FetcherSession
        url (str): Recipe URL
        title (str): Recipe title
        card_meta (dict): Metadata scraped from the list card
        
    Returns:
        dict: Complete recipe object or None if scraping fails.
    """
    try:
        response = session.get(url)
        time.sleep(1.2) # Polite delay to respect server
        
        content_div = response.css_first('div.gz-content-recipe.gz-mBottom4x')
        if not content_div:
            return None

        # Description extraction: Remove trailing colons from the last fragment
        desc_fragments = content_div.css('p:not(.gz-translation-link) ::text').get_all()
        if desc_fragments:
            desc_fragments[-1] = desc_fragments[-1].replace(":", "")
        full_description = clean_data(" ".join(desc_fragments))

        # Related Recipes extraction
        related = []
        related_section = content_div.css('li')
        for r in related_section:
            r_name = r.css('::text').get()
            a_tag = r.css_first('a')
            r_url = a_tag.attrib.get('href') if a_tag else None
            if r_name and r_url:
                related.append({"name": r_name.strip(), "url": r_url})

        # Build final flat object
        recipe_data = {
            "title": title.strip() if title else "Untitled",
            "url": url,
            "description": full_description,
            "ingredients": parse_ingredients(response),
            "instructions": parse_instructions(response),
            "related_recipes": related,
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            # Flattened Metadata
            "category": card_meta.get("category"),
            "prep_time": card_meta.get("prep_time"),
            "calories": card_meta.get("calories"),
            "difficulty": card_meta.get("rating") # Renamed from rating to difficulty
        }

        return recipe_data
    except Exception as e:
        logging.error(f"Error scraping detail page {url}: {e}")
        return None

def get_list_page_data(session, url, base_url):
    """
    Parses a category list page to extract recipe links and metadata.
    
    Returns:
        tuple: (list of recipe dicts, next_page_url)
    """
    try:
        response = session.get(url)
        cards = response.css('article.gz-card')
        
        page_recipes = []
        for card in cards:
            title_node = card.css_first('h2.gz-title a')
            if not title_node: continue
            
            recipe_title = title_node.text
            recipe_url = urljoin(base_url, title_node.attrib.get('href'))
            
            # Default values
            prep_time, calories, rating = "Not Available", "Not Available", "Not Available"
            footer_items = card.css('li.gz-single-data-recipe')
            
            # Parse footer items (time, kcal, difficulty) based on content content
            for item in footer_items:
                clean_text_val = "".join(item.css('::text').get_all()).strip()
                if "min" in clean_text_val or "h" in clean_text_val:
                    prep_time = clean_text_val
                elif "Kcal" in clean_text_val:
                    calories = clean_text_val.replace("Kcal", "").replace(",", ".").strip()
                else:
                    try:
                        # Attempt to parse difficulty rating as a number
                        val = clean_text_val.replace(',', '.').strip()
                        float(val)
                        rating = val
                    except ValueError: pass

            meta = {
                "category": (card.css('div.gz-category ::text').get() or "Not Available").strip(),
                "prep_time": prep_time,
                "calories": calories,
                "rating": rating
            }
            page_recipes.append({"title": recipe_title, "url": recipe_url, "meta": meta})
        
        next_node = response.css_first('a.gz-arrow.next')
        next_url = urljoin(base_url, next_node.attrib.get('href')) if next_node else None
        
        return page_recipes, next_url
    except Exception as e:
        logging.error(f"Error on list page {url}: {e}")
        return [], None

# --- MAIN EXECUTION ---

def main():
    base_domain = "https://www.giallozafferano.it"
    # Starting point: Main recipe category page
    current_url = urljoin(base_domain, "ricette-cat/")
    
    # Flag to stop pagination if we hit an existing recipe
    stop_scraping = False

    with FetcherSession() as session:
        while current_url and not stop_scraping:
            logging.info(f"Checking Page: {current_url}")
            recipe_links, next_page = get_list_page_data(session, current_url, base_domain)
            
            if not recipe_links:
                break

            for entry in recipe_links:
                # 1. Check if the URL already exists in MongoDB
                if collection.find_one({"url": entry['url']}):
                    logging.info(f"Found match in DB for '{entry['title']}'. Stopping incremental scrape.")
                    stop_scraping = True
                    break # Exit the recipe loop
                
                # 2. If it's new, scrape the details
                logging.info(f"Scraping NEW recipe: {entry['title']}")
                data = scrape_recipe_detail(session, entry['url'], entry['title'], entry['meta'])
                
                # 3. Insert immediately into MongoDB
                if data:
                    collection.insert_one(data)
                    logging.info(f"Successfully inserted: {entry['title']}")
            
            current_url = next_page
            time.sleep(2) # Prevent rate limiting

    logging.info("Scrape finished. Database is up to date.")

if __name__ == "__main__":
    main()