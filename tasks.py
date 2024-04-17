import logging
import os
import re
import requests
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from RPA.Browser.Selenium import Selenium
from RPA.Excel.Files import Files
from robocorp import workitems
from robocorp.tasks import task


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(funcName)s - %(message)s')
logger = logging.getLogger(__name__)


def search_news(browser, search_phrase):
    try:
        browser.click_element_if_visible('//*[@class="site-header__search-trigger"]')
        search_input = WebDriverWait(browser.driver, 60).until(EC.visibility_of_element_located((By.XPATH, '//*[@class="search-bar__input"]')))
        browser.input_text(search_input, search_phrase)
        browser.press_keys(search_input, Keys.ENTER)

        sort_by_date = WebDriverWait(browser.driver, 60).until(EC.visibility_of_element_located((By.XPATH, '//*[@id="search-sort-option"]')))
        browser.click_button_when_visible(sort_by_date)
        browser.select_from_list_by_value('//*[@id="search-sort-option"]', 'date')

        WebDriverWait(browser.driver, 60).until(EC.visibility_of_element_located((By.XPATH, '//*[@class="search-result__list"]')))

    except Exception as e:
        logger.error(f"Failed to perform search or select date option. Error: {e}")


def extract_articles(browser, target_date):
    article_elements = []

    while True:
        try:
            browser.wait_until_element_is_visible('class:search-result__list')
            soup = BeautifulSoup(browser.get_source(), 'html.parser')
            article_elements = soup.find_all("article", class_="gc u-clickable-card gc--type-customsearch#result gc--list gc--with-image")

            last_article_date = get_article_date(article_elements[-1])
            if last_article_date and last_article_date < target_date:
                break

            show_more_button = WebDriverWait(browser.driver, 60).until(EC.presence_of_element_located((By.CSS_SELECTOR, "button.show-more-button")))
            browser.click_element_when_clickable(show_more_button)

        except TimeoutException as e:
            logger.error(f"Timeout waiting for 'Show more' button: {e}")
            break

        except Exception as e:
            logger.error(f"Error extracting articles: {e}")
            break

    return article_elements


def get_article_date(article_element):
    try:
        date_element = article_element.find("div", class_="gc__date__date")
        if date_element:
            date_text = date_element.find("span", attrs={"aria-hidden": True}).get_text(strip=True)
            return parse_article_date(date_text)

        excerpt_element = article_element.find("div", class_="gc__excerpt")
        if excerpt_element:
            excerpt_text = excerpt_element.find("p").get_text(strip=True)
            return parse_relative_date(excerpt_text)

    except Exception as e:
        logger.error(f"Error parsing article date: {e}")
        return None


def parse_article_date(date_text):
    date_formats = ["Last update %d %b %Y", "%d %b %Y"]
    for date_format in date_formats:
        try:
            return datetime.strptime(date_text, date_format)
        except ValueError:
            continue
    return None


def parse_relative_date(text):
    relative_time_pattern = re.compile(r"(\d+)\s+(hour|hours|day|days|minute|minutes|year|years)\s+ago")
    match = relative_time_pattern.search(text)
    if match:
        num_units = int(match.group(1))
        time_unit = match.group(2)
        delta = timedelta(**{f"{time_unit}s": num_units})
        return datetime.now() - delta
    return None


def clean_string(input_string):
    cleaned_string = re.sub(r"\b\d+\s+\w+\s+ago\b", "", input_string)
    cleaned_string = cleaned_string.replace("...", "").strip()
    cleaned_string = re.sub(r"\s+", " ", cleaned_string)
    return cleaned_string


def process_news_data(articles, target_date, search_phrase):
    workbook = Files()
    workbook.create_workbook(path="./output/news_data.xlsx", fmt="xlsx", sheet_name="News Articles")

    table = []
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
            'Title': title,
            'Date': date.strftime("%d %b %Y") if date else "",
            'Description': clean_string(description),
            'Image URI': image_uri,
            'Count Phrases': count_phrases,
            'Contains Money': "True" if contains_money else "False",
        })

    workbook.append_rows_to_worksheet(table, header=True)
    workbook.save_workbook()


def download_image(url, output_dir='output/images', filename=None):
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
    browser.open_available_browser(url, maximized=True)


@task
def minimal_task():
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
