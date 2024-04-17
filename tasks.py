import logging
import os
import re
import requests
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, ElementNotVisibleException
from selenium.webdriver.support import expected_conditions as EC


from RPA.Browser.Selenium import Selenium
from RPA.Excel.Files import Files
from robocorp import workitems
from robocorp.tasks import task

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(funcName)s - %(message)s')
logger = logging.getLogger(__name__)


def search_news(browser, search_phrase):
    """
    Search news based on a given search phrase.

    Args:
        browser (Selenium): RPA Browser instance.
        search_phrase (str): The search phrase to use for news search.
    """
    try:
        browser.click_element_if_visible('//*[@class="site-header__search-trigger"]')

        search_input = WebDriverWait(browser.driver, 60, 0.5, ignored_exceptions=[TimeoutException]).until(EC.visibility_of_element_located((By.XPATH, '//*[@class="search-bar__input"]')))
        browser.input_text(search_input, search_phrase)

        browser.press_keys(search_input, Keys.ENTER)

        sort_by_date = WebDriverWait(browser.driver, 60, 0.5, ignored_exceptions=[TimeoutException]).until(EC.visibility_of_element_located((By.XPATH, '//*[@id="search-sort-option"]')))
        browser.click_button_when_visible(sort_by_date)

        browser.select_from_list_by_value('//*[@id="search-sort-option"]', 'date')

        WebDriverWait(browser.driver,60, 0.5, ignored_exceptions=[TimeoutException, ElementNotVisibleException]).until(EC.visibility_of_element_located((By.XPATH, '//*[@class="search-result__list"]')))

    except Exception as e:
        logger.error(f"Failed to perform search or select date option. Error: {e}")



def extract_articles(browser, target_date):
    """
    Extract articles based on the target date.

    Args:
        browser (Selenium): RPA Browser instance.
        target_date (datetime): Target date to filter articles.

    Returns:
        list: List of BeautifulSoup article elements.
    """
    article_elements = []

    while True:
        try:
            show_more_button = WebDriverWait(browser.driver, 60, 0.5, ignored_exceptions=[TimeoutException]).until(EC.presence_of_element_located((By.CLASS_NAME, 'search-result__list')))
            browser.wait_until_element_is_visible('class:search-result__list')
            soup = BeautifulSoup(browser.get_source(), 'html.parser')
            article_elements = soup.find_all("article", class_="gc u-clickable-card gc--type-customsearch#result gc--list gc--with-image")

            last_article_date = get_article_date(article_elements[-1])
            if last_article_date and last_article_date < target_date:
                break

            show_more_button = WebDriverWait(browser.driver, 60, 0.5, ignored_exceptions=[TimeoutException]).until(EC.presence_of_element_located((By.CSS_SELECTOR, "button.show-more-button")))
            browser.click_element_when_clickable(show_more_button)

        except TimeoutException as e:
            logger.error(f"Timeout waiting for 'Show more' button : {e}")
            break

        except Exception as e:
            logger.error(f"Error extracting articles: {e}")
            break

    return article_elements


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
    except Exception:
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
    return None


def process_news_data(articles, target_date, search_phrase):
    """
    Process extracted news articles and save to Excel.

    Args:
        articles (list): List of BeautifulSoup article elements.
        target_date (datetime): Target date to filter articles.
        search_phrase (str): The search phrase used for news search.
    """
    workbook = Files()
    workbook.create_workbook(path="./output/news_data.xlsx", fmt="xlsx", sheet_name="News Articles")

    table =[]
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
        contains_money = bool(re.search(r"\$[\d,]+(\.\d+)?|\d+\s?(dollars|USD)", title, re.IGNORECASE)) or bool(re.search(r"\$[\d,]+(\.\d+)?|\d+\s?(dollars|USD)", description, re.IGNORECASE))
        table.append({
            'Title':title,
            'Date':date.strftime("%d %b %Y") if date else "",
            'Description':description,
            'Image URI':image_uri,
            'Count Phrases':count_phrases,
            'Contains Money':"True" if contains_money else "False",
        })
    workbook.append_rows_to_worksheet(table, header=True)
    workbook.save_workbook()


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
        response.raise_for_status()

        os.makedirs(output_dir, exist_ok=True)

        if not filename:
            filename = os.path.basename(url)
        save_path = os.path.join(output_dir, filename)

        with open(save_path, 'wb') as file:
            file.write(response.content)

        return save_path

    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading image: {e}")
        return None


def open_the_intranet_website(browser, url):
    """Navigates to the given URL and maximizes the browser window."""
    browser.open_available_browser(url, maximized=True)


@task
def minimal_task():
    """
    Task to perform minimal news scraping based on input parameters.
    Expects input parameters 'search_phrase' (str) and 'num_months' (int) from work item.
    """
    browser = Selenium()
    try:
        search_options = workitems.inputs.current.payload["input_search_phrase"]
        search_phrase = search_options["search_phrase"]
        num_months = int(search_options["num_months"])
        url = "https://www.aljazeera.com/"

        browser.set_download_directory("output/images")
        open_the_intranet_website(browser, url)
        search_news(browser, search_phrase)

        target_date = datetime.now() - timedelta(days=30 * num_months)
        articles = extract_articles(browser, target_date)
        process_news_data(articles, target_date, search_phrase)

        logger.info(f"Scraping {search_phrase} completed successfully!")

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")

    finally:
        if browser:
            browser.close_all_browsers()
        logger.warning("Cleaning up completed.")

