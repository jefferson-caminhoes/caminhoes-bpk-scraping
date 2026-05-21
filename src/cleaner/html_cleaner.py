import re
from bs4 import BeautifulSoup, Comment


_REMOVE_TAGS = ["script", "style", "head", "nav", "footer", "header", "svg", "noscript"]


def clean_html(raw_html: str) -> str:
    if not raw_html or not raw_html.strip():
        return ""

    soup = BeautifulSoup(raw_html, "lxml")

    # Remove unwanted tags
    for tag_name in _REMOVE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Remove HTML comments
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Convert tables to readable text before extracting
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if any(cols):
                rows.append(" | ".join(cols))
        table.replace_with("\n".join(rows))

    text = soup.get_text(separator="\n")

    # Normalize whitespace
    lines = [line.strip() for line in text.splitlines()]
    # Remove duplicate consecutive lines
    deduped = []
    prev = None
    for line in lines:
        if line and line != prev:
            deduped.append(line)
            prev = line

    return "\n".join(deduped)
