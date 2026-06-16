import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "site_output"


def fail(message):
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def assert_exists(path):
    if not path.exists():
        fail(f"missing {path.relative_to(ROOT)}")


def assert_clean_html(path):
    source = path.read_text(encoding="utf-8")
    forbidden = [
        "url_for(",
        "personal.",
        "☰",
        "🌙",
        "☀",
        "✕",
        "▶",
        "▼",
        "↗",
        "&rarr;",
        "&larr;",
    ]
    hits = [token for token in forbidden if token in source]
    if hits:
        fail(f"{path.relative_to(ROOT)} contains {hits}")
    if '<meta charset="utf-8">' not in source:
        fail(f"{path.relative_to(ROOT)} is missing UTF-8 meta tag")


def main():
    required = [
        OUTPUT_DIR / "index.html",
        OUTPUT_DIR / "archive" / "index.html",
        OUTPUT_DIR / "about" / "index.html",
        OUTPUT_DIR / "sources" / "index.html",
        OUTPUT_DIR / "404.html",
        OUTPUT_DIR / "500.html",
    ]
    for path in required:
        assert_exists(path)
        assert_clean_html(path)

    story_pages = sorted((OUTPUT_DIR / "stories").glob("*/index.html"))
    article_pages = sorted((OUTPUT_DIR / "articles").glob("*/index.html"))
    edition_pages = sorted((OUTPUT_DIR / "editions").glob("*/*/index.html"))

    if not story_pages:
        fail("no story pages exported")
    if not article_pages:
        fail("no article pages exported")
    if not edition_pages:
        fail("no edition pages exported")

    for path in [story_pages[0], article_pages[0], edition_pages[0]]:
        assert_clean_html(path)

    print(
        "OK: static export smoke check passed "
        f"({len(edition_pages)} editions, {len(story_pages)} stories, {len(article_pages)} articles)"
    )


if __name__ == "__main__":
    main()
