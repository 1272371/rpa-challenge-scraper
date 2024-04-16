import os
import logging
import requests
from datetime import datetime
from selenium import webdriver

def init_browser(browser_type="chrome"):
    """Initialize Selenium WebDriver."""
    if browser_type.lower() == "chrome":
        return webdriver.Chrome()
    else:
        return webdriver.Firefox()

def download_image(url, output_dir='output/images', filename=None):
    """
    Download an image from the specified URL and save it to the specified directory with the given filename.

    Args:
        url (str): URL of the image to download.
        output_dir (str): Directory where the downloaded image will be saved.
        filename (str): The name of the file to save the image as. If None, the filename is extracted from the URL.

    Returns:
        str or None: File path of the downloaded image if successful, None otherwise.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Create the output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Use the provided filename or extract it from the URL if not provided
        if not filename:
            filename = os.path.basename(url)
        save_path = os.path.join(output_dir, filename)

        with open(save_path, 'wb') as file:
            file.write(response.content)

        logger.info(f"Image downloaded successfully and saved to: {save_path}")
        return save_path  # Return the file path of the downloaded image

    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading image: {e}")
        return None

def get_article_date(article_element):
    """Extract article date from the HTML element."""
    try:
        # date_element = article_element.find("div", class_="gc__date gc__date--published")
        date_element = article_element.find("div", class_="gc__date__date")
        if date_element:
            date_text = date_element.find("span", attrs={"aria-hidden": True}).get_text(strip=True)
            return parse_article_date(date_text) 
    except Exception as e:
        logging.warning(f"Failed to extract date from article: {e}")
    return None

def parse_article_date(date_text):
    """Parse article date with specified date formats."""
    date_formats = ["Last update %d %b %Y", "%d %b %Y"]
    return parse_with_formats(date_text, date_formats)

def parse_with_formats(text, formats):
    """Try parsing text with multiple date formats."""
    for date_format in formats:
        try:
            return datetime.strptime(text, date_format)
        except ValueError:
            continue
    logging.warning("Failed to parse date with any of the specified formats.")
    return None
