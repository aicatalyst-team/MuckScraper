import logging
import math
import os
import shutil
from io import BytesIO
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests
from flask import Flask, render_template
from jinja2 import ChoiceLoader, FileSystemLoader

from aggregator import db
from aggregator.constants import AGGREGATORS
from aggregator.filters import register_filters
from aggregator.article_signals import is_roundup_article
from aggregator.models import Article, Edition, EditionStory

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "private_site" / "templates"
OUTPUT_DIR = ROOT / "site_output"
STATIC_SOURCE = ROOT / "aggregator" / "static"
IMAGE_OUTPUT_DIR = OUTPUT_DIR / "images"
PER_PAGE = int(os.environ.get("MUCKSCRAPER_STATIC_PER_PAGE", "5"))
ARCHIVE_IMAGE_MAX_WIDTH = int(os.environ.get("MUCKSCRAPER_ARCHIVE_IMAGE_MAX_WIDTH", "1200"))
ARCHIVE_IMAGE_TARGET_BYTES = int(os.environ.get("MUCKSCRAPER_ARCHIVE_IMAGE_TARGET_BYTES", str(300 * 1024)))
ARCHIVE_IMAGE_TIMEOUT = int(os.environ.get("MUCKSCRAPER_ARCHIVE_IMAGE_TIMEOUT", "15"))
ARCHIVE_IMAGE_MIN_WIDTH = int(os.environ.get("MUCKSCRAPER_ARCHIVE_IMAGE_MIN_WIDTH", "480"))
ARCHIVE_IMAGE_MIN_HEIGHT = int(os.environ.get("MUCKSCRAPER_ARCHIVE_IMAGE_MIN_HEIGHT", "270"))
NON_IMAGE_EXTENSIONS = {".m3u8", ".mp4", ".m4v", ".mov", ".webm", ".avi"}

EDITION_LABELS = {
    "night": "Night Edition",
    "morning": "Morning Edition",
    "afternoon": "Afternoon Edition",
    "evening": "Evening Edition",
}


def create_export_app():
    app = Flask(
        __name__,
        template_folder=str(TEMPLATE_DIR),
        static_folder=str(STATIC_SOURCE),
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        raise RuntimeError(
            "SECRET_KEY environment variable must be set (see .env.sample)"
        )
    app.config["SECRET_KEY"] = secret_key

    db.init_app(app)
    register_filters(app)

    app.jinja_loader = ChoiceLoader([
        FileSystemLoader(str(TEMPLATE_DIR)),
        app.jinja_loader,
    ])
    app.jinja_env.globals["url_for"] = static_url_for
    return app


def static_url_for(endpoint, **values):
    filename = values.pop("filename", None)
    page = values.pop("page", None)

    if endpoint == "static":
        return f"/static/{filename}"
    if endpoint in {"personal.headlines", "public.index"}:
        return page_path(page)
    if endpoint == "personal.archive_page":
        return "/archive/index.html"
    if endpoint == "personal.about":
        return "/about/index.html"
    if endpoint == "personal.sources":
        return "/sources/index.html"
    if endpoint == "personal.view_edition":
        return edition_path(values["date"], values["edition_type"], page)
    if endpoint == "personal.public_story":
        return story_path(
            values["story_id"],
            values.get("date"),
            values.get("edition_type"),
            page,
        )
    if endpoint == "personal.public_article":
        return article_path(
            values["article_id"],
            values.get("date"),
            values.get("edition_type"),
            page,
        )

    logger.warning("No static URL mapping for endpoint %s", endpoint)
    return "#"


def page_path(page=None):
    page = int(page or 1)
    if page <= 1:
        return "/index.html"
    return f"/page/{page}/index.html"


def edition_path(date, edition_type, page=None):
    page = int(page or 1)
    base = f"/editions/{date}/{edition_type}"
    if page <= 1:
        return f"{base}/index.html"
    return f"{base}/page/{page}/index.html"


def story_path(story_id, date=None, edition_type=None, page=None):
    if date and edition_type:
        page = int(page or 1)
        base = f"/editions/{date}/{edition_type}"
        if page <= 1:
            return f"{base}/stories/{story_id}/index.html"
        return f"{base}/page/{page}/stories/{story_id}/index.html"
    return f"/stories/{story_id}/index.html"


def article_path(article_id, date=None, edition_type=None, page=None):
    if date and edition_type:
        page = int(page or 1)
        base = f"/editions/{date}/{edition_type}"
        if page <= 1:
            return f"{base}/articles/{article_id}/index.html"
        return f"{base}/page/{page}/articles/{article_id}/index.html"
    return f"/articles/{article_id}/index.html"


def write_page(path, html):
    target = OUTPUT_DIR / path.lstrip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return target


def copy_static_assets():
    destination = OUTPUT_DIR / "static"
    if destination.exists():
        shutil.rmtree(destination)
    if STATIC_SOURCE.exists():
        shutil.copytree(STATIC_SOURCE, destination)


def story_articles_for_image(story):
    articles = getattr(story, "display_articles", None)
    if articles:
        articles = list(articles)
    else:
        articles = sorted(
            story.articles,
            key=lambda article: article.date or article.fetched_at or datetime.min,
            reverse=True,
        )

    eligible = [
        article for article in articles
        if not is_roundup_article(article.title, article.url)
    ]
    if eligible:
        return eligible

    if getattr(story, "display_articles", None):
        return list(story.display_articles)
    return sorted(
        story.articles,
        key=lambda article: article.date or article.fetched_at or datetime.min,
        reverse=True,
    )


def edition_story_image_relpath(edition_story):
    edition = edition_story.edition
    return (
        f"/images/{edition.date.isoformat()}/{edition.edition_type}/"
        f"story-{edition_story.story_id}.jpg"
    )


def archive_image_target_path(relative_path):
    return OUTPUT_DIR / relative_path.lstrip("/")


def clear_archived_image(edition_story, status):
    edition_story.archived_image_path = None
    edition_story.source_image_url = None
    edition_story.image_credit_text = None
    edition_story.image_download_status = status
    edition_story.image_downloaded_at = None
    edition_story.image_width = None
    edition_story.image_height = None
    edition_story.image_bytes = None


def image_credit_for_article(article):
    outlet = getattr(article, "outlet", None)
    if outlet and outlet.name:
        return outlet.name
    return "Original source"


def looks_like_image_url(url):
    path = urlparse(url).path.lower()
    return not any(path.endswith(ext) for ext in NON_IMAGE_EXTENSIONS)


def compress_image_bytes(raw_bytes):
    from PIL import Image, UnidentifiedImageError

    with Image.open(BytesIO(raw_bytes)) as image:
        image = image.convert("RGB")
        if image.width < ARCHIVE_IMAGE_MIN_WIDTH or image.height < ARCHIVE_IMAGE_MIN_HEIGHT:
            raise ValueError(
                f"image too small {image.width}x{image.height}; "
                f"minimum is {ARCHIVE_IMAGE_MIN_WIDTH}x{ARCHIVE_IMAGE_MIN_HEIGHT}"
            )
        if image.width > ARCHIVE_IMAGE_MAX_WIDTH:
            ratio = ARCHIVE_IMAGE_MAX_WIDTH / float(image.width)
            new_height = max(1, int(image.height * ratio))
            image = image.resize((ARCHIVE_IMAGE_MAX_WIDTH, new_height), Image.Resampling.LANCZOS)

        qualities = [82, 74, 66, 58, 50, 42]
        best_payload = None
        best_quality = None
        for quality in qualities:
            output = BytesIO()
            image.save(output, format="JPEG", quality=quality, optimize=True, progressive=True)
            payload = output.getvalue()
            best_payload = payload
            best_quality = quality
            if len(payload) <= ARCHIVE_IMAGE_TARGET_BYTES:
                break

        return {
            "payload": best_payload,
            "width": image.width,
            "height": image.height,
            "bytes": len(best_payload) if best_payload else 0,
            "quality": best_quality,
        }


def download_story_image(edition_story):
    relative_path = edition_story_image_relpath(edition_story)
    target_path = archive_image_target_path(relative_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    for article in story_articles_for_image(edition_story.story):
        image_url = (article.image_url or "").strip()
        if not image_url:
            continue
        if not looks_like_image_url(image_url):
            logger.info(
                "[Static Export] Skipping non-image URL for story %s: %s",
                edition_story.story_id,
                image_url,
            )
            continue

        try:
            response = requests.get(image_url, timeout=ARCHIVE_IMAGE_TIMEOUT)
            response.raise_for_status()
            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type and not content_type.startswith("image/"):
                raise ValueError(f"unexpected content type {content_type}")
            image_data = compress_image_bytes(response.content)
        except (requests.RequestException, OSError, ValueError) as exc:
            logger.info(
                "[Static Export] Image archive failed for story %s from %s: %s",
                edition_story.story_id,
                image_url,
                exc,
            )
            continue
        except Exception as exc:
            logger.info(
                "[Static Export] Image archive failed for story %s from %s: %s",
                edition_story.story_id,
                image_url,
                exc,
            )
            continue

        target_path.write_bytes(image_data["payload"])
        edition_story.archived_image_path = relative_path
        edition_story.source_image_url = image_url
        edition_story.image_credit_text = image_credit_for_article(article)
        edition_story.image_download_status = "downloaded"
        edition_story.image_downloaded_at = datetime.utcnow()
        edition_story.image_width = image_data["width"]
        edition_story.image_height = image_data["height"]
        edition_story.image_bytes = image_data["bytes"]
        return True

    has_candidate = any((article.image_url or "").strip() for article in edition_story.story.articles)
    clear_archived_image(edition_story, "failed" if has_candidate else "none_available")
    return False


def ensure_edition_story_image(edition_story):
    if not getattr(edition_story, "story", None):
        clear_archived_image(edition_story, "no_story")
        return

    relative_path = edition_story.archived_image_path
    if relative_path:
        target_path = archive_image_target_path(relative_path)
        if target_path.exists():
            if (
                edition_story.image_width is not None and
                edition_story.image_height is not None and
                (
                    edition_story.image_width < ARCHIVE_IMAGE_MIN_WIDTH or
                    edition_story.image_height < ARCHIVE_IMAGE_MIN_HEIGHT
                )
            ):
                logger.info(
                    "[Static Export] Replacing low-resolution archived image for story %s: %sx%s",
                    edition_story.story_id,
                    edition_story.image_width,
                    edition_story.image_height,
                )
            else:
                if not edition_story.image_download_status:
                    edition_story.image_download_status = "downloaded"
                return
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        clear_archived_image(edition_story, "too_small")

    download_story_image(edition_story)


def apply_aggregator_filter(story):
    originals = []
    aggregators = []
    has_good_original = False
    seen_articles = set()
    sorted_articles = sorted(
        story.articles,
        key=lambda article: article.date or datetime.min,
        reverse=True,
    )

    for article in sorted_articles:
        key = (article.title, article.outlet_id)
        if key in seen_articles:
            continue
        seen_articles.add(key)
        outlet_name = article.outlet.name if article.outlet else ""
        if any(agg in outlet_name for agg in AGGREGATORS):
            aggregators.append(article)
        else:
            originals.append(article)
            if article.content and len(article.content) > 500:
                has_good_original = True

    story.display_articles = originals if has_good_original else originals + aggregators
    if not has_good_original:
        story.display_articles.sort(
            key=lambda article: article.date or datetime.min,
            reverse=True,
        )

    unique_outlets = []
    seen_outlet_ids = set()
    for article in story.display_articles:
        if article.outlet_id and article.outlet_id not in seen_outlet_ids:
            unique_outlets.append(article.outlet)
            seen_outlet_ids.add(article.outlet_id)
    story.unique_outlets = unique_outlets

    status_counts = {
        "success": 0,
        "fallback": 0,
        "blocked": 0,
    }
    for article in story.display_articles:
        status = (article.scrape_status or "blocked").lower()
        if status == "success":
            status_counts["success"] += 1
        elif status == "fallback":
            status_counts["fallback"] += 1
        else:
            status_counts["blocked"] += 1

    total_articles = len(story.display_articles)
    total_unique_outlets = len(story.unique_outlets)
    story.display_article_count = total_articles
    story.display_outlet_count = total_unique_outlets
    readable_articles = status_counts["success"] + status_counts["fallback"]
    story.scrape_quality = {
        "total": total_articles,
        "outlets": total_unique_outlets,
        "success": status_counts["success"],
        "fallback": status_counts["fallback"],
        "blocked": status_counts["blocked"],
        "readable_pct": round((readable_articles / total_articles) * 100) if total_articles else 0,
        "full_pct": round((status_counts["success"] / total_articles) * 100) if total_articles else 0,
    }


def get_menu_recent():
    cutoff = datetime.utcnow().date() - timedelta(days=7)
    editions = Edition.query.filter(
        Edition.date >= cutoff,
        Edition.published == True,
    ).order_by(Edition.date.desc(), Edition.created_at.desc()).all()

    grouped = defaultdict(list)
    for edition in editions:
        grouped[edition.date.strftime("%A, %b %d")].append(edition)
    return list(grouped.items())


def get_archive_all():
    editions = Edition.query.filter(
        Edition.published == True,
    ).order_by(Edition.date.desc(), Edition.created_at.desc()).all()

    grouped = defaultdict(lambda: defaultdict(list))
    for edition in editions:
        month_key = edition.date.strftime("%B %Y")
        day_key = edition.date.strftime("%A, %B %d")
        grouped[month_key][day_key].append(edition)

    result = []
    sorted_months = sorted(
        grouped.keys(),
        key=lambda month: datetime.strptime(month, "%B %Y"),
        reverse=True,
    )
    for month in sorted_months:
        days = []
        sorted_days = sorted(
            grouped[month].keys(),
            key=lambda day: datetime.strptime(day, "%A, %B %d"),
            reverse=True,
        )
        for day in sorted_days:
            days.append((day, grouped[month][day]))
        result.append((month, days))
    return result


def get_latest_edition():
    return Edition.query.filter_by(published=True).order_by(
        Edition.created_at.desc()
    ).first()


def get_edition_stories(edition):
    edition_stories = edition.edition_stories.order_by(EditionStory.rank).all()
    stories = []
    for edition_story in edition_stories:
        story = edition_story.story
        if not story:
            logger.warning(
                "[Static Export] Skipping edition story %s with no linked story.",
                edition_story.id,
            )
            continue
        if not story.articles:
            logger.warning(
                "[Static Export] Skipping story %s in edition %s %s because it has no articles.",
                story.id,
                edition.date.isoformat(),
                edition.edition_type,
            )
            clear_archived_image(edition_story, "no_articles")
            continue
        apply_aggregator_filter(story)
        ensure_edition_story_image(edition_story)
        story.edition_has_updates = bool(getattr(edition_story, "has_updates", False))
        story.edition_story = edition_story
        story.archived_image_path = edition_story.archived_image_path
        story.archived_image_credit = edition_story.image_credit_text
        story.archived_image_source_url = edition_story.source_image_url
        stories.append(story)
    return stories


def render_edition_page(edition, page, stories, menu_recent, latest_edition):
    total_pages = max(1, math.ceil(len(stories) / PER_PAGE))
    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE
    page_stories = stories[start:end]
    edition_label = EDITION_LABELS.get(
        edition.edition_type,
        f"{edition.edition_type.title()} Edition",
    )

    html = render_template(
        "headlines.html",
        stories=page_stories,
        edition=edition,
        edition_label=edition_label,
        edition_date_display=edition.date.strftime("%A, %B %d, %Y").upper(),
        menu_recent=menu_recent,
        is_latest=edition.id == latest_edition.id if latest_edition else False,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
    return html


def export_edition(edition, menu_recent, latest_edition, include_subpages=True):
    stories = get_edition_stories(edition)
    total_pages = max(1, math.ceil(len(stories) / PER_PAGE))

    for page in range(1, total_pages + 1):
        html = render_edition_page(edition, page, stories, menu_recent, latest_edition)
        write_page(
            edition_path(edition.date.isoformat(), edition.edition_type, page),
            html,
        )
        if latest_edition and edition.id == latest_edition.id:
            write_page(page_path(page), html)

        if not include_subpages:
            continue

        start = (page - 1) * PER_PAGE
        end = start + PER_PAGE
        for story in stories[start:end]:
            export_story(story, edition, back_page=page)


def export_story(story, edition, back_page=None):
    if not story.articles:
        logger.warning(
            "[Static Export] Skipping story page export for story %s because it has no articles.",
            story.id,
        )
        return

    apply_aggregator_filter(story)
    menu_recent = get_menu_recent()
    back_date = edition.date.isoformat() if edition else None
    back_type = edition.edition_type if edition else None
    back_page = back_page or 1
    edition_story = None
    if edition:
        edition_story = edition.edition_stories.filter_by(story_id=story.id).first()
        if edition_story:
            ensure_edition_story_image(edition_story)

    if len(story.articles) > 1:
        html = render_template(
            "public_story.html",
            story=story,
            edition_story=edition_story,
            menu_recent=menu_recent,
            back_date=back_date,
            back_type=back_type,
            back_page=back_page,
        )
        write_page(story_path(story.id, back_date, back_type, back_page), html)

    for article in story.articles:
        export_article(article, back_date, back_type, back_page, edition_story)


def export_article(article, back_date=None, back_type=None, back_page=None, edition_story=None):
    menu_recent = get_menu_recent()
    back_page = back_page or 1
    html = render_template(
        "public_article.html",
        article=article,
        edition_story=edition_story,
        menu_recent=menu_recent,
        back_date=back_date,
        back_type=back_type,
        back_page=back_page,
    )
    write_page(article_path(article.id, back_date, back_type, back_page), html)


def export_support_pages():
    menu_recent = get_menu_recent()
    write_page(
        "/archive/index.html",
        render_template(
            "archive.html",
            archive_data=get_archive_all(),
            menu_recent=menu_recent,
        ),
    )
    write_page(
        "/about/index.html",
        render_template("about.html", menu_recent=menu_recent),
    )
    write_page(
        "/sources/index.html",
        render_template("sources.html", menu_recent=menu_recent),
    )
    write_page("/404.html", render_template("404.html"))
    write_page("/500.html", render_template("500.html"))


def _env_flag(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def export_static_site(full_archive=None):
    app = create_export_app()
    with app.app_context():
        if full_archive is None:
            full_archive = _env_flag("MUCKSCRAPER_STATIC_FULL_ARCHIVE", False)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        copy_static_assets()

        latest_edition = get_latest_edition()
        if not latest_edition:
            logger.info("[Static Export] No published editions found.")
            export_support_pages()
            return

        menu_recent = get_menu_recent()
        if full_archive:
            editions = Edition.query.filter_by(published=True).order_by(
                Edition.date.desc(),
                Edition.created_at.desc(),
            ).all()
            for edition in editions:
                export_edition(edition, menu_recent, latest_edition)
        else:
            editions = [latest_edition]
            export_edition(latest_edition, menu_recent, latest_edition)

            # Other editions still listed in the "Recent Editions" sidebar were
            # exported on earlier runs with a stale menu_recent that didn't yet
            # include this latest edition. Refresh just their index pages so the
            # sidebar shows the current edition list everywhere.
            for _, eds in menu_recent:
                for edition in eds:
                    if edition.id != latest_edition.id:
                        export_edition(edition, menu_recent, latest_edition, include_subpages=False)

        db.session.commit()
        export_support_pages()
        logger.info(
            "[Static Export] Exported %s edition%s to %s%s",
            len(editions),
            "" if len(editions) == 1 else "s",
            OUTPUT_DIR,
            " (full archive)" if full_archive else " (latest only)",
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    export_static_site()
