#!/usr/bin/env python3
"""Prepare Chronicle's static website in a new, empty directory."""

import argparse
from datetime import datetime
from html import escape
import json
from pathlib import Path
import re
import shutil

PROJECT_URL = "https://github.com/harry6116/Chronicle"
RELEASE_START = "<!-- RELEASE_ANNOUNCEMENT_START -->"
RELEASE_END = "<!-- RELEASE_ANNOUNCEMENT_END -->"


def release_content(release):
    if release is None:
        return (
            '<aside id="release-announcement" aria-labelledby="release-title">'
            '<h3 id="release-title">Latest update</h3>'
            f'<p><a href="{PROJECT_URL}/releases/latest">See the latest release</a>.</p></aside>',
            "Latest Chronicle release", "Release details are available on GitHub.",
            PROJECT_URL + "/releases/latest",
        )
    tag = release.get("tag_name", "")
    if release.get("draft") is not False or release.get("prerelease") is not False:
        raise ValueError("Only a published stable release may be announced.")
    if not isinstance(tag, str) or not re.fullmatch(r"v?\d+\.\d+\.\d+(?:\.\d+)?", tag):
        raise ValueError("A release version is required.")
    url = release.get("html_url", "")
    if url != PROJECT_URL + "/releases/tag/" + tag:
        raise ValueError("The release link must identify this Chronicle release.")
    try:
        published = datetime.fromisoformat(release["published_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        raise ValueError("A valid publication date is required.") from error
    assets = {item.get("name") for item in release.get("assets", [])
              if item.get("state") == "uploaded" and item.get("size", 0) > 0}
    if not {"Chronicle.mac.zip", "Chronicle.windows.zip"}.issubset(assets):
        raise ValueError("Both completed Mac and Windows downloads are required.")
    title = "Chronicle " + tag.removeprefix("v")
    notes = release.get("body") or "No release notes were provided."
    if not isinstance(notes, str):
        raise ValueError("Release notes must be text.")
    highlights = []
    for line in notes.splitlines():
        if re.match(r"^[-*] ", line):
            text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line[2:])
            text = text.replace("**", "").replace("`", "")
            highlights.append(escape(text[:220]))
        if len(highlights) == 3:
            break
    date = published.date().isoformat()
    summary = "<ul>" + "".join(f"<li>{item}</li>" for item in highlights) + "</ul>" if highlights else ""
    announcement = (
        '<aside id="release-announcement" aria-labelledby="release-title">'
        '<h3 id="release-title">Latest update</h3>'
        f'<p><strong>{escape(title)}</strong> — released <time datetime="{date}">{published:%d %B %Y}</time>.</p>'
        + summary + '<p><a href="release-notes.html">Read the full release notes</a></p></aside>'
    )
    return announcement, title, notes, url


def notes_blocks(notes, title):
    blocks = []
    paragraph = []
    in_list = False

    def inline(text):
        text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
        return escape(text.replace("**", "").replace("`", ""))

    def flush_paragraph():
        if paragraph:
            blocks.append("<p>" + inline(" ".join(paragraph)) + "</p>")
            paragraph.clear()

    for line in notes.splitlines():
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        bullet = re.match(r"^[-*]\s+(.+)$", line)
        if in_list and not bullet:
            blocks.append("</ul>")
            in_list = False
        if heading:
            flush_paragraph()
            if heading[2].strip() != title:
                level = max(2, min(6, len(heading[1])))
                blocks.append(f"<h{level}>{inline(heading[2])}</h{level}>")
        elif bullet:
            flush_paragraph()
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append("<li>" + inline(bullet[1]) + "</li>")
        elif line.strip():
            paragraph.append(line.strip())
        else:
            flush_paragraph()
    flush_paragraph()
    if in_list:
        blocks.append("</ul>")
    return "\n".join(blocks)


def notes_page(title, notes, url):
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} — release notes</title>
<style>body {{font:1.125rem/1.6 system-ui,sans-serif;color:#172331;background:#f7f8fc;max-width:70ch;margin:2rem auto;padding:0 1.25rem}} a {{color:#245484}} a:focus-visible {{outline:3px solid #9a5200;outline-offset:4px}} .notes {{overflow-wrap:anywhere}} </style>
</head><body><a href="#notes">Skip to release notes</a><nav aria-label="Release navigation"><p><a href="index.html">Back to Chronicle</a> · <a href="{escape(url, quote=True)}">View this release on GitHub</a></p></nav>
<main id="notes"><h1>{escape(title)} — release notes</h1><div class="notes">{notes_blocks(notes, title)}</div></main></body></html>'''


def build_site(repo_root, output, *, release=None):
    repo_root, output = Path(repo_root).resolve(), Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Website output must be empty.")
    announcement, title, notes, url = release_content(release)
    public = repo_root / "docs/public"
    if (public / "index.html").is_symlink():
        raise ValueError("Website sources must not contain symbolic links.")
    index = (public / "index.html").read_text(encoding="utf-8")
    pattern = re.escape(RELEASE_START) + r".*?" + re.escape(RELEASE_END)
    index, count = re.subn(pattern, lambda _match: announcement, index, flags=re.DOTALL)
    if count != 1:
        raise ValueError("Exactly one release announcement location is required.")
    files = [(repo_root / "docs/user/chronicle_help.html", Path("user-guide.html"))]
    for folder in ("showcase_assets", "showcase_samples"):
        for source in sorted((public / folder).rglob("*")):
            if source.is_symlink():
                raise ValueError("Website sources must not contain symbolic links.")
            if source.is_file() and source.suffix.lower() in {".html", ".png", ".jpg", ".jpeg", ".svg"}:
                files.append((source, source.relative_to(public)))
    for source, relative in files:
        if source.is_symlink():
            raise ValueError("Website sources must not contain symbolic links.")
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (output / "index.html").write_text(index, encoding="utf-8")
    (output / "release-notes.html").write_text(notes_page(title, notes, url), encoding="utf-8")
    (output / ".nojekyll").touch()
    return len(files) + 3


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--release-json", help="Latest published release metadata from the GitHub API.")
    args = parser.parse_args()
    release = json.loads(Path(args.release_json).read_text(encoding="utf-8")) if args.release_json else None
    print(f"Prepared {build_site(Path(__file__).resolve().parents[1], args.output, release=release)} website files.")
