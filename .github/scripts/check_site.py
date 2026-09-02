#!/usr/bin/env python3
"""Pre-flight checks for rosefinancialmanagement.com.

    python3 check_site.py <site-root> [--fix-sitemap]

Exit 0 = clear. Exit 1 = at least one blocking problem.
Every check here exists because that problem actually occurred.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

DOMAIN = "rosefinancialmanagement.com"
UNPROVISIONED_EMAIL = "kevin@rosefinancialmanagement.com"
REQUIRED_FILES = ["CNAME", "404.html", "robots.txt", "sitemap.xml", "index.html"]
# Pages served but never listed in the sitemap. Only the error page belongs
# here. paper-trail.html was considered and deliberately left OUT of this set
# (Aug 24): it is unlinked from site navigation, which keeps it word-of-mouth,
# but it stays indexable so someone who half-remembers it can search for it.
UNLISTED = {"404.html"}

# --- Rollover disclosure (38-LPL) ---------------------------------------
# LPL requires the four-option disclosure, verbatim, on any material that
# discusses IRA rollovers. Flagged by Ken Lam in ART, Jul 21 2026.
# Detected by a distinctive fragment so wrapping and punctuation can vary.
ROLLOVER_RE = re.compile(r"\broll(ing|ed|s)?[ -]?(it |the |your |over\b)|\brollover", re.I)
DISCLOSURE_SENTINEL = "typically has four options"

# Superseded three-option framing. Corrected sitewide Jul 25 2026 but it
# survived in meta tags, which is what Google prints as the search snippet.
BANNED_PHRASES = [
    "keep it, roll it, or split it",
    "keep, roll, or split",
    "keep it, roll it or split it",
]
SKIP_DIRS = {".git", ".github", "node_modules", ".idea", ".vscode"}
INTERNAL_EXT = {".md", ".py", ".sh", ".docx", ".xlsx", ".pptx", ".zip", ".bak", ".log"}
INTERNAL_NAME_RE = re.compile(
    r"(handoff|outline|draft|internal|case-|notes?|todo|pom|practice-ops|manifest)",
    re.I,
)
PLACEHOLDER_RE = re.compile(r"(TODO|FIXME|XXX|LOREM IPSUM|\bTK\b|PLACEHOLDER|\[INSERT)", re.I)
# Build notes are invisible in a browser but readable in view-source. One saying
# the disclosures were unapproved sat on all 19 pages from launch until Aug 2026.
# Checked against raw HTML, not visible text, because that is how it survived.
BUILD_NOTE_RE = re.compile(
    r"<!--(?:(?!-->).)*?\b("
    r"language to be (supplied|provided|approved)"
    r"|to be (supplied|provided|drafted|written) by"
    r"|final (copy|language|disclosure)[^>]{0,40}\bTBD\b"
    r"|\bTBD\b|\bLOREM\b|\bFIXME\b|\bXXX\b"
    r")",
    re.I | re.S,
)
GLOB_JUNK_RE = re.compile(r"[\*\?\[\]]|\{.*,.*\}")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
VOID = {"area","base","br","col","embed","hr","img","input","link","meta",
        "param","source","track","wbr"}

blocks, warns, notes = [], [], []


def block(msg): blocks.append(msg)
def warn(msg): warns.append(msg)
def note(msg): notes.append(msg)


class TagBalance(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.bad = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for orphan, line in self.stack[i + 1:]:
                    self.bad.append(f"<{orphan}> opened line {line} never closed")
                del self.stack[i:]
                return
        self.bad.append(f"</{tag}> at line {self.getpos()[0]} closes nothing")


def visible_text(html: str) -> str:
    s = COMMENT_RE.sub(" ", html)
    s = SCRIPT_STYLE_RE.sub(" ", s)
    return TAG_RE.sub(" ", s)


def html_files(root: Path):
    for p in sorted(root.rglob("*.html")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def check_page(root: Path, path: Path, plausible_seen: list):
    rel = path.relative_to(root).as_posix()
    raw = path.read_text(encoding="utf-8", errors="replace")
    text = visible_text(raw)

    tb = TagBalance()
    try:
        tb.feed(raw)
        tb.close()
    except Exception as e:
        block(f"{rel}: HTML failed to parse ({e})")
    for orphan, line in tb.stack:
        tb.bad.append(f"<{orphan}> opened line {line} never closed")
    for b in tb.bad[:5]:
        block(f"{rel}: {b}")

    if "\u2014" in text:
        snippet = text[max(0, text.index("\u2014") - 45): text.index("\u2014") + 45]
        block(f'{rel}: em-dash in visible copy near "{" ".join(snippet.split())}"')

    m = PLACEHOLDER_RE.search(text)
    if m:
        block(f"{rel}: placeholder text {m.group(0)!r} in visible copy")

    m = BUILD_NOTE_RE.search(raw)
    if m:
        block(f"{rel}: unfinished-copy note left in an HTML comment "
              f"({m.group(1)!r}). Invisible in a browser, readable in view-source.")

    if UNPROVISIONED_EMAIL in raw.lower():
        block(f"{rel}: unprovisioned RFM email address present")

    low = raw.lower()
    for phrase in BANNED_PHRASES:
        if phrase in low:
            block(f"{rel}: superseded three-option TSP framing {phrase!r} "
                  f"(check meta, og and twitter description tags, not just body copy)")

    # Rollover content must carry the 38-LPL disclosure verbatim. Checked
    # against the whole file so meta tags count as discussing it too.
    if ROLLOVER_RE.search(raw) and DISCLOSURE_SENTINEL not in low:
        block(f"{rel}: discusses rollovers without the 38-LPL four-option "
              f"disclosure (required verbatim, not paraphrased)")

    # Absolute self-links in <a> and asset tags only. Canonical, og:url and
    # schema URLs are *required* to be absolute, so they are not faults.
    self_re = re.compile(
        r'<(a|img|script|iframe|source)\b[^>]*?(?:href|src)\s*=\s*["\']'
        r'(https?://(?:www\.)?' + re.escape(DOMAIN) + r'[^"\']*)',
        re.I,
    )
    m = self_re.search(raw)
    if m:
        block(f"{rel}: absolute self-link in <{m.group(1).lower()}> -> {m.group(2)} "
              f"(use a relative path; this is the class of bug that 404'd the booking button)")

    if re.search(r'<form[^>]+action\s*=\s*["\']?\s*mailto:', raw, re.I):
        block(f"{rel}: form posts to mailto:")

    for m in re.finditer(r'<script[^>]+type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                         raw, re.S | re.I):
        try:
            json.loads(m.group(1))
        except json.JSONDecodeError as e:
            block(f"{rel}: JSON-LD does not parse ({e.msg} line {e.lineno})")

    for attr in ("href", "src"):
        for m in re.finditer(attr + r'\s*=\s*["\']([^"\']+)["\']', raw, re.I):
            target = m.group(1).strip()
            if (not target or target.startswith(("#", "mailto:", "tel:", "javascript:", "data:"))
                    or urlparse(target).scheme in ("http", "https")):
                continue
            clean = unquote(target.split("#")[0].split("?")[0])
            if not clean:
                continue
            dest = (root / clean.lstrip("/")) if clean.startswith("/") else (path.parent / clean)
            if dest.is_dir():
                dest = dest / "index.html"
            if not dest.exists():
                block(f"{rel}: broken link -> {target}")

    # A complete Plausible install is two tags: the library and an init call.
    # The library alone loads and silently sends nothing, which is exactly the
    # partial install this check exists to catch. Shipped on one page Sep 2026.
    if re.search(r'plausible\.io/js/', raw, re.I):
        if 'plausible.init(' in raw:
            plausible_seen.append(rel)
        else:
            block(f"{rel}: Plausible library loaded without plausible.init(). "
                  f"The script loads and records nothing.")
    if rel != "404.html":
        if not re.search(r'<link[^>]+rel\s*=\s*["\']canonical', raw, re.I):
            warn(f"{rel}: no canonical tag")
        if not re.search(r'<meta[^>]+name\s*=\s*["\']description', raw, re.I):
            warn(f"{rel}: no meta description")
    for m in re.finditer(r"<img\b[^>]*>", raw, re.I):
        if not re.search(r'\balt\s*=', m.group(0), re.I):
            warn(f"{rel}: <img> without alt text")
            break


def check_structure(root: Path):
    for f in REQUIRED_FILES:
        if not (root / f).exists():
            block(f"missing required file: {f}")

    cname = root / "CNAME"
    if cname.exists():
        val = cname.read_text(encoding="utf-8").strip()
        if val != DOMAIN:
            block(f"CNAME reads {val!r}, expected {DOMAIN!r}")

    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(part in SKIP_DIRS for part in p.parts):
            continue
        rel = p.relative_to(root).as_posix()
        if GLOB_JUNK_RE.search(p.name):
            block(f"junk path from an unexpanded glob: {rel}")
        if p.suffix.lower() in INTERNAL_EXT and p.name not in ("README.md",):
            block(f"internal document in the web root: {rel}")
        elif p.suffix.lower() == ".html" and INTERNAL_NAME_RE.search(p.stem):
            warn(f"filename looks internal: {rel}")


def site_urls(root: Path):
    """Every publicly served URL, in sitemap form. Directories -> trailing slash."""
    urls = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() not in (".html", ".pdf"):
            continue
        rel = p.relative_to(root).as_posix()
        if rel in UNLISTED:
            continue
        if p.name == "index.html":
            rel = rel[: -len("index.html")]
        urls.append(f"https://{DOMAIN}/{rel}")
    return sorted(set(urls))


def git_date(root: Path, p: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(p.relative_to(root))],
            cwd=root, capture_output=True, text=True, timeout=20,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    ts = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    return ts.date().isoformat()


def build_sitemap(root: Path) -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in site_urls(root):
        rel = url[len(f"https://{DOMAIN}/"):]
        p = root / (rel + "index.html" if rel.endswith("/") or rel == "" else rel)
        if rel == "":
            p = root / "index.html"
        lastmod = git_date(root, p) if p.exists() else date.today().isoformat()
        depth = rel.rstrip("/").count("/")
        pri = "1.0" if rel == "" else ("0.8" if depth == 0 or rel.endswith("/") else "0.6")
        lines.append(f"  <url>\n    <loc>{url}</loc>\n"
                     f"    <lastmod>{lastmod}</lastmod>\n"
                     f"    <priority>{pri}</priority>\n  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def check_sitemap(root: Path, fix: bool):
    path = root / "sitemap.xml"
    expected = build_sitemap(root)
    if fix:
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current != expected:
            path.write_text(expected, encoding="utf-8")
            note(f"sitemap.xml regenerated ({len(site_urls(root))} URLs)")
        else:
            note("sitemap.xml already current")
        return
    if not path.exists():
        return
    have = set(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", path.read_text(encoding="utf-8")))
    want = set(site_urls(root))
    for missing in sorted(want - have):
        warn(f"sitemap missing: {missing}")
    for extra in sorted(have - want):
        warn(f"sitemap lists a URL with no file: {extra}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--fix-sitemap", action="store_true",
                    help="rewrite sitemap.xml from the file tree instead of only reporting")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"not a directory: {root}")

    check_structure(root)
    plausible_seen = []
    pages = list(html_files(root))
    for p in pages:
        check_page(root, p, plausible_seen)

    tracked = [p.relative_to(root).as_posix() for p in pages
               if p.relative_to(root).as_posix() != "404.html"]
    if plausible_seen and len(plausible_seen) < len(tracked):
        for miss in sorted(set(tracked) - set(plausible_seen)):
            warn(f"{miss}: no Plausible script (partial install produces wrong data)")
    elif plausible_seen:
        note(f"Plausible present on all {len(plausible_seen)} pages")

    check_sitemap(root, args.fix_sitemap)

    for n in notes:
        print(f"note   {n}")
    for w in warns:
        print(f"WARN   {w}")
    for b in blocks:
        print(f"BLOCK  {b}")
    print(f"\n{len(pages)} pages checked · {len(blocks)} blocking · {len(warns)} warnings")
    if args.fix_sitemap:
        # Regeneration must not fail the build, or the commit step never runs
        # and the rebuilt sitemap is thrown away. The later check step gates.
        sys.exit(0)
    sys.exit(1 if blocks else 0)


if __name__ == "__main__":
    main()
