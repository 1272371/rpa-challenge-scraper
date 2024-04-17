
def process_news_data(articles, target_date, search_phrase):
    """
    Process extracted news articles and save to Excel.

    Args:
        articles (list): List of BeautifulSoup article elements.
        target_date (datetime): Target date to filter articles.
        search_phrase (str): The search phrase used for news search.
    """
    workbook = Files()
    sheet = workbook.create_worksheet(title="News Articles", fmt="xlsx")  # Removed path argument for using default location
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
        contains_money = bool(re.search(r'\$[\d,]+(\.\d+)?|\d+\s?(dollars|USD)', title, re.IGNORECASE)) or bool(re.search(r'\$[\d,]+(\.\d+)?|\d+\s?(dollars|USD)', description, re.IGNORECASE))

        sheet.append([
            title,
            date.strftime("%d %b %Y") if date else "",
            description,
            image_uri,
            count_phrases,
            "True" if contains_money else "False"
        ])

    workbook.save(filename='output/news_data.xlsx')  # Changed filename for saving to 'output' directory

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

        return save_path  # Return the file path of the downloaded image

    except requests.exceptions.RequestException as e:
        logger.log(f"Error downloading image: {e}", level='ERROR')
        return None
