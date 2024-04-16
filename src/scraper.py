import re
import logging
from bs4 import BeautifulSoup
from openpyxl import Workbook
from utils import download_image, get_article_date
from bs4 import BeautifulSoup
from openpyxl import Workbook
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)

def search_news(browser, search_phrase):
    """Search news based on a given search phrase."""
    browser.get("https://www.aljazeera.com/")
    browser.maximize_window()

    # Perform search
    search_trigger = browser.find_element(By.CSS_SELECTOR, ".site-header__search-trigger")
    search_trigger.click()

    search_input = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".search-bar__input")))
    search_input.clear()
    search_input.send_keys(search_phrase)
    search_input.send_keys(Keys.RETURN)

    # Sort by date
    try:
        sort_dropdown = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "search-sort-option")))
        sort_dropdown.click()
        date_option = WebDriverWait(browser, 5).until(EC.element_to_be_clickable((By.XPATH, "//option[@value='date']")))
        date_option.click()
        WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".search-result__list")))
    except TimeoutException:
        logging.warning("Failed to select date option in the sort dropdown")

def extract_articles(browser, target_date):
    """Extract articles based on the target date."""
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
    """Process extracted news articles and save to Excel."""
    money_pattern = re.compile(r'\$[\d,]+(\.\d+)?|\d+\s?(dollars|USD)', re.IGNORECASE)

    # Create a new workbook
    workbook = Workbook()
    sheet = workbook.active

    # Add headers to the first row
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
        image_uri = download_image(image_url, filename = f"img - %s" % idx)
        count_phrases = title.lower().count(search_phrase.lower()) + description.lower().count(search_phrase.lower())
        contains_money = bool(money_pattern.search(title)) or bool(money_pattern.search(description))

        # Append article data to the sheet
        sheet.append([
            title,
            date.strftime("%d %b %Y") if date else "",
            description,
            image_uri,
            count_phrases,
            "True" if contains_money else "False"
        ])

    # Save the workbook to a file
    workbook.save('news_data.xlsx')
