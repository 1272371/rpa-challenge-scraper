import os
import re
import requests
import logging
from bs4 import BeautifulSoup
from selenium import webdriver
from openpyxl import Workbook
from datetime import datetime
from datetime import timedelta
from robocorp import workitems
from robocorp.tasks import task
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(funcName)s - %(message)s')
logger = logging.getLogger(__name__)

def search_news(browser, search_phrase):
    """
    Search news based on a given search phrase.

    Args:
        browser (webdriver): Selenium WebDriver instance.
        search_phrase (str): The search phrase to use for news search.
    """
    try:
        search_trigger = browser.find_element(By.CSS_SELECTOR, ".site-header__search-trigger")
        search_trigger.click()

        search_input = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".search-bar__input")))
        search_input.clear()
        search_input.send_keys(search_phrase)
        search_input.send_keys(Keys.RETURN)

        # Sort by date
        sort_dropdown = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "search-sort-option")))
        sort_dropdown.click()

        date_option = WebDriverWait(browser, 5).until(EC.element_to_be_clickable((By.XPATH, "//option[@value='date']")))
        date_option.click()

        WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".search-result__list")))
    except TimeoutException:
        logging.warning("Failed to perform search or select date option.")

def extract_articles(browser, target_date):
    """
    Extract articles based on the target date.

    Args:
        browser (webdriver): Selenium WebDriver instance.
        target_date (datetime): Target date to filter articles.

    Returns:
        list: List of BeautifulSoup article elements.
    """
    article_elements = []

    while True:
        WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".gc__title")))
        soup = BeautifulSoup(browser.page_source, 'html.parser')
        article_elements = soup.find_all("article", class_="gc u-clickable-card gc--type-customsearch#result gc--list gc--with-image")

        last_article_date = get_article_date(article_elements[-1])
        if last_article_date and last_article_date < target_date:
            break

        try:
            show_more_button = WebDriverWait(browser, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "button.show-more-button")))
            browser.execute_script("arguments[0].click();", show_more_button)
        except TimeoutException:
            break

    return article_elements

def process_news_data(articles, target_date, search_phrase):
    """
    Process extracted news articles and save to Excel.

    Args:
        articles (list): List of BeautifulSoup article elements.
        target_date (datetime): Target date to filter articles.
        search_phrase (str): The search phrase used for news search.
    """
    money_pattern = re.compile(r'\$[\d,]+(\.\d+)?|\d+\s?(dollars|USD)', re.IGNORECASE)

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['Title', 'Date', 'Description', 'Image URI', 'Count Phrases', 'Contains Money'])

    for idx, article in enumerate(articles):
        title_element = article.find("h3", class_="gc__title").find("a")
        if not title_element:
            continue

        title = title_element.text.strip()
        date = get_article_date(article)

        if date and date < target_date:
            break

        description_element = article.find("div", class_="gc__excerpt").find("p")
        description = description_element.get_text(strip=True) if description_element else ""
        image_element = article.find("img", class_="gc__image")
        image_url = image_element["src"] if image_element else ""
        image_uri = download_image(image_url, filename=f"img-{idx}")
        count_phrases = title.lower().count(search_phrase.lower()) + description.lower().count(search_phrase.lower())
        contains_money = bool(money_pattern.search(title)) or bool(money_pattern.search(description))

        sheet.append([
            title,
            date.strftime("%d %b %Y") if date else "",
            description,
            image_uri,
            count_phrases,
            "True" if contains_money else "False"
        ])

    workbook.save('news_data.xlsx')

def init_browser_handler(browser_type="chrome", driver_path=None, options=None):
    """
    Initialize Selenium WebDriver based on specified browser type.

    Args:
        browser_type (str): Browser type to initialize ('chrome' or 'firefox').
        driver_path (str): Path to the WebDriver executable (optional).
        options (dict): Dictionary of browser-specific options (optional).

    Returns:
        webdriver: Initialized Selenium WebDriver instance.
    """
    if browser_type.lower() == "chrome":
        chrome_options = ChromeOptions()
        if options and "headless" in options:
            chrome_options.add_argument("--headless")
        if driver_path:
            return webdriver.Chrome(executable_path=driver_path, options=chrome_options)
        else:
            return webdriver.Chrome(options=chrome_options)

    elif browser_type.lower() == "firefox":
        firefox_options = FirefoxOptions()
        if options and "headless" in options:
            firefox_options.add_argument("--headless")
        if driver_path:
            return webdriver.Firefox(executable_path=driver_path, options=firefox_options)
        else:
            return webdriver.Firefox(options=firefox_options)

    else:
        raise ValueError("Unsupported browser type.")

def open_browser(browser):
    """
    Open the specified browser and navigate to a default URL.

    Args:
        browser (webdriver): Selenium WebDriver instance to use.
    """
    try:
        browser.get("https://www.aljazeera.com/")
        browser.maximize_window()

    except WebDriverException as e:
        logging.error(f"WebDriverException occurred: {e}")

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

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
    """
    Extract article date from the HTML element.

    Args:
        article_element (BeautifulSoup): BeautifulSoup element representing the article.

    Returns:
        datetime or None: Extracted datetime object representing the article date, or None if not found.
    """
    try:
        date_element = article_element.find("div", class_="gc__date__date")
        if date_element:
            date_text = date_element.find("span", attrs={"aria-hidden": True}).get_text(strip=True)
            return parse_article_date(date_text)
    except Exception as e:
        logging.warning(f"Failed to extract date from article: {e}")
    return None

def parse_article_date(date_text):
    """
    Parse article date with specified date formats.

    Args:
        date_text (str): Text representation of the article date.

    Returns:
        datetime or None: Parsed datetime object representing the article date, or None if parsing fails.
    """
    date_formats = ["Last update %d %b %Y", "%d %b %Y"]
    return parse_with_formats(date_text, date_formats)

def parse_with_formats(text, formats):
    """
    Try parsing text with multiple date formats.

    Args:
        text (str): Text representation of the date to parse.
        formats (list): List of date formats to attempt parsing.

    Returns:
        datetime or None: Parsed datetime object representing the date, or None if parsing fails.
    """
    for date_format in formats:
        try:
            return datetime.strptime(text, date_format)
        except ValueError:
            continue
    logging.warning("Failed to parse date with any of the specified formats.")
    return None


@task
def minimal_task():
    """
    Task to perform minimal news scraping based on input parameters.
    Expects input parameters 'search_phrase' (str) and 'num_months' (int) from work item.
    """
    browser = None
    try:
        # Retrieve search options from work item inputs
        search_options = workitems.inputs.current.payload["input_search_phrase"]

        search_phrase = search_options["search_phrase"]
        num_months = int(search_options["num_months"])

        browser = init_browser_handler(browser_type="chrome", driver_path="chromedriver", options=None)
        open_browser(browser)
        search_news(browser, search_phrase)
        target_date = datetime.now() - timedelta(days=30 * num_months)
        articles = extract_articles(browser, target_date)
        process_news_data(articles, target_date, search_phrase)
        logging.info(f"Scraping {search_phrase} completed successfully!")

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")

    finally:
        if browser:
            browser.quit()
        logging.info("Cleaning up completed.")







# @task
# def create_work_item_task():
#     """
#     Task to programmatically create a Robocloud work item with specified parameters.

#     Arguments:
#         search_phrase (str): The search phrase for news scraping.
#         months (int): Number of months to look back for news articles.

#     Usage:
#         create_work_item_task("AI", 2)
#     """
#     search_phrase = "AI"
#     months = 1
#     # Define your Robocloud API credentials
#     api_key = 'n0quinMUdxzsyCnu85iZho8mWr248fpy5x67bXdXIe0FjSujUibUwuwSqdOi9gIGJWtRhRQtlI7TqUDb2unjW5g7byqrVdAurx5eBQJZamzVnivHqHyoHn1gPTfuW7PmH'
#     workspace_id = 'Harmony Mncube'
#     # Specify the task to execute and input parameters
#     task_name = 'Harmony Mncube'

#     payload = {
#         'search_phrase': search_phrase,
#         'num_months': months
#     }

#     # Attempt to create the work item with the specified task and input parameters
#     try:
#         item = dict(input_search_phrase=payload)
#         response = workitems.outputs.create(item)
#         print(f": {response}")
#     except Exception as e:
#         print(f"Error creating work item: {str(e)}")

#     for item in workitems.inputs:
#         search_options = item.payload
#         print(search_options)
