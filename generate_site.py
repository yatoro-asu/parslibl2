import json
from math import ceil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from more_itertools import chunked

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
BOOKS_PATH = BASE_DIR / "books.json"
OUTPUT_PATH = BASE_DIR / "index.html"
LOCAL_IMAGES_DIR = BASE_DIR / "static" / "images"
PAGE_SIZE = 10


def normalize_book(book: dict) -> dict:
    title = book.get("title") or "Без названия"
    author = book.get("author") or "Не указан"
    image_url = book.get("image_url") or book.get("cover") or ""
    image_name = image_url.rsplit("/", 1)[-1]
    local_image = LOCAL_IMAGES_DIR / image_name
    cover = f"static/images/{image_name}" if image_name and local_image.exists() else image_url
    genre = book.get("genre") or ""
    genres = [item.strip() for item in genre.split("/") if item.strip()]
    description = book.get("description") or "Книга из библиотеки проекта."
    alt = book.get("alt") or f"Обложка книги {title}"
    text_url = book.get("text_url") or ""

    return {
        "title": title,
        "author": author,
        "cover": cover,
        "genres": genres,
        "description": description,
        "alt": alt,
        "text_url": text_url,
    }


def get_page_numbers(current_page: int, total_pages: int) -> list[int]:
    if total_pages <= 7:
        return list(range(1, total_pages + 1))

    pages = list(range(1, total_pages + 1))
    start = max(1, current_page - 3)
    end = min(total_pages, current_page + 3)

    if current_page <= 4:
        start = 1
        end = 7
    elif current_page >= total_pages - 3:
        start = total_pages - 6
        end = total_pages

    return pages[start - 1:end]


def render_page(books: list[dict], page_number: int, total_pages: int) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("books_template.html")

    rows = list(chunked(books, 2))
    page_numbers = get_page_numbers(page_number, total_pages)

    return template.render(
        rows=rows,
        page_number=page_number,
        total_pages=total_pages,
        page_numbers=page_numbers,
        prev_page=max(1, page_number - 1),
        next_page=min(total_pages, page_number + 1),
        has_prev=page_number > 1,
        has_next=page_number < total_pages,
    )


def main() -> None:
    with open(BOOKS_PATH, "r", encoding="utf-8") as file:
        books = json.load(file)

    normalized_books = [normalize_book(book) for book in books]
    total_pages = max(1, ceil(len(normalized_books) / PAGE_SIZE))

    for page_number in range(1, total_pages + 1):
        start = (page_number - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        page_books = normalized_books[start:end]
        html = render_page(page_books, page_number, total_pages)

        filename = "index.html" if page_number == 1 else f"index-{page_number}.html"
        (BASE_DIR / filename).write_text(html, encoding="utf-8")

    print(f"Сгенерировано: {OUTPUT_PATH} ({len(normalized_books)} книг, {total_pages} страниц)")


if __name__ == "__main__":
    main()
