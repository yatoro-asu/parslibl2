import argparse
import json
import os
import time
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from sanitize_filename import sanitize

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FOLDER = BASE_DIR / "images11"
BOOKS_FOLDER = BASE_DIR / "books"
BOOKS_JSON = BASE_DIR / "books.json"
FANTASY_URL = "https://knigofil.org/fighting-fantasy/"
FANTASY_PAGE_TEMPLATE = "https://knigofil.org/fighting-fantasy/page/{page}/"
FANTASY_CATEGORY = "fighting-fantasy"


def get_filename_from_url(url: str) -> str:
    url_path = urlsplit(url).path
    filename = os.path.split(url_path)[1]
    filename = unquote(filename)
    if not filename:
        filename = "downloaded_image.jpg"
    name, extension = os.path.splitext(filename)
    if not extension:
        filename = f"{name}.jpg"
    return filename


def normalize_book_link(href: str) -> str:
    library_url = "https://knigofil.org/"
    if href.startswith("/"):
        return library_url.rstrip("/") + href
    if not href.startswith("http"):
        return library_url.rstrip("/") + "/" + href
    return href


def fetch_page(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    retries = 3
    delay = 1
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as error:
            if attempt == retries:
                raise
            print(f"Ошибка запроса ({url}): {error}. Повтор через {delay} сек.")
            time.sleep(delay)
            delay *= 2


def get_all_book_links(html: str, category: str | None = None) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    links: list[str] = []

    for a in soup.find_all("a", class_="book-link"):
        href: str = str(a.get("href") or "")
        if not href:
            continue
        href = normalize_book_link(href)
        if category and category not in href:
            continue
        if href not in seen:
            seen.add(href)
            links.append(href)

    return links


def get_fantasy_page_links(page_number: int) -> list[str]:
    if page_number <= 1:
        page_url = FANTASY_URL
    else:
        page_url = FANTASY_PAGE_TEMPLATE.format(page=page_number)

    try:
        html = fetch_page(page_url)
    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as error:
        print(f"Ошибка при загрузке страницы фантастики {page_number}: {error}")
        return []

    return get_all_book_links(html, category=FANTASY_CATEGORY)


def get_fantasy_links(start_page: int = 1, end_page: int = 10) -> list[str]:
    fantasy_links: list[str] = []
    for page_number in range(start_page, end_page + 1):
        page_links = get_fantasy_page_links(page_number)
        print(f"Ссылок на странице {page_number}: {len(page_links)}")
        for link in page_links:
            if link not in fantasy_links:
                fantasy_links.append(link)
        time.sleep(1)
    return fantasy_links


def get_book_info(book_page_html: str) -> dict:
    soup = BeautifulSoup(book_page_html, "html.parser")

    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)

    author = ""
    genre = ""
    year = ""

    for stat in soup.find_all("div", class_="big-book-stat"):
        span = stat.find("span")
        if not span:
            continue
        key = span.get_text(strip=True).rstrip(":")
        values = [a.get_text(strip=True) for a in stat.find_all("a")]
        value = " / ".join(values)
        if key == "Автор":
            author = value
        elif key == "Жанр":
            genre = value
        elif key == "Год":
            year = value

    return {"title": title, "author": author, "genre": genre, "year": year}


def get_book_image_url(book_page_html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(book_page_html, "html.parser")

    container = soup.find("div", class_="big-book-left-block")
    image = container.find("img") if container else None

    if not image:
        container = soup.find("div", class_="book-wrapper")
        image = container.find("img") if container else None

    if not image:
        for image_tag in soup.find_all("img"):
            src = str(image_tag.get("src") or "")
            if "uploads/posts" in src:
                image = image_tag
                break

    if image:
        image_url = str(image.get("src") or "")
        if image_url:
            return urljoin(base_url, image_url)
    return None


def get_book_txt_url(book_page_html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(book_page_html, "html.parser")
    for link in soup.find_all("a", href=True):
        href = str(link.get("href") or "")
        if href.lower().split("?", 1)[0].endswith(".txt"):
            return urljoin(base_url, href)
    return None


def get_fantasy_books(fantasy_links: list[str]) -> list[dict]:
    books: list[dict] = []
    for i, url in enumerate(fantasy_links, 1):
        try:
            html = fetch_page(url)
        except (
            requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ) as error:
            print(f"  {i}. Ошибка страницы книги: {error}")
            continue

        info = get_book_info(html)
        if not info["title"]:
            print(f"  {i}. Пропускаю книгу без названия: {url}")
            continue

        books.append(
            {
                "title": info["title"],
                "author": info["author"],
                "genre": info["genre"],
                "release": info["year"],
                "url": url,
                "image_url": get_book_image_url(html, url),
                "text_url": get_book_txt_url(html, url),
            }
        )
    return books


def save_books_json(books: list[dict], output_file: str | Path = BOOKS_JSON) -> None:
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(books, file, ensure_ascii=False, indent=4)


def print_download_links(books: list[dict]) -> None:
    for book in books:
        image_url = book["image_url"]
        text_url = book["text_url"]
        if image_url is None or text_url is None:
            print(f"  Ссылки не найдены: {book['title']}")
            continue
        print(f"  Обложка: {image_url}")
        print(f"  Текст: {text_url}")


def download_fantasy_books(
    books: list[dict], skip_imgs: bool = False, skip_txt: bool = False
) -> None:
    for i, book in enumerate(books, 1):
        try:
            if not skip_imgs and book["image_url"] is not None:
                image_path = download_image(book["image_url"], OUTPUT_FOLDER)
                book["img_src"] = str(Path(image_path).relative_to(BASE_DIR)).replace(
                    "\\", "/"
                )
            if not skip_txt and book["text_url"] is not None:
                text_path = download_book_text(
                    book["text_url"], book["title"], BOOKS_FOLDER
                )
                book["book_path"] = str(Path(text_path).relative_to(BASE_DIR)).replace(
                    "\\", "/"
                )
            print(f"  {i}. Скачано: {book['title']}")
        except (
            requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ) as error:
            print(f"  {i}. Ошибка скачивания {book['title']}: {error}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Скачивание книг и обложек из раздела боевой фантастики."
    )
    parser.add_argument(
        "start_page", nargs="?", type=int, default=1,
        help="Номер начальной страницы (по умолчанию: 1).",
    )
    parser.add_argument(
        "end_page", nargs="?", type=int, default=10,
        help="Номер конечной страницы (по умолчанию: 10).",
    )
    parser.add_argument(
        "--skip_imgs", "--skip-imgs", action="store_true",
        help="Не скачивать обложки.",
    )
    parser.add_argument(
        "--skip_txt", "--skip-txt", action="store_true",
        help="Не скачивать тексты.",
    )
    args = parser.parse_args()
    if args.start_page < 1 or args.end_page < args.start_page:
        parser.error("Нужен корректный диапазон страниц: start_page <= end_page.")
    return args


def download_image(url: str, output_folder: str | Path = OUTPUT_FOLDER) -> str:
    filename = get_filename_from_url(url)
    output_folder_path = Path(output_folder)
    output_folder_path.mkdir(parents=True, exist_ok=True)
    output_path = output_folder_path / filename

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(response.content)

    return str(output_path)


def download_book_text(
    txt_url: str, title: str, output_folder: str | Path = BOOKS_FOLDER
) -> str:
    output_folder_path = Path(output_folder)
    output_folder_path.mkdir(parents=True, exist_ok=True)

    filename = sanitize(title or get_filename_from_url(txt_url))
    if not filename.endswith(".txt"):
        filename += ".txt"
    output_path = output_folder_path / filename

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    response = requests.get(txt_url, headers=headers, timeout=30)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(response.content)

    return str(output_path)


def main() -> None:
    args = parse_args()
    print(
        f"Получаю ссылки на страницы фантастики с {args.start_page} по {args.end_page}..."
    )
    fantasy_links = get_fantasy_links(args.start_page, args.end_page)
    print(f"Всего ссылок на фантастику из 10 страниц: {len(fantasy_links)}")
    print()

    print("Шаг 6: собираю информацию о книгах и сохраняю books.json...")
    fantasy_books = get_fantasy_books(fantasy_links)
    save_books_json(fantasy_books)
    print(f"Сохранено книг: {len(fantasy_books)}\n")

    print("Шаг 7: проверяю ссылки на обложки и тексты...")
    print_download_links(fantasy_books)
    print()

    print("Шаг 8: скачиваю книги и обложки из фантастики...")
    download_fantasy_books(fantasy_books, args.skip_imgs, args.skip_txt)
    save_books_json(fantasy_books)
    print("\nГотово.")


if __name__ == "__main__":
    main()
