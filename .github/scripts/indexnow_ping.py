#!/usr/bin/env python3
"""Submit every sitemap URL to IndexNow. Run after each deploy.

    python3 indexnow_ping.py /path/to/site

Finds the key file at the site root, reads sitemap.xml, submits in one call.
IndexNow feeds Bing, Yandex, Seznam, Naver. Google does not participate.
"""
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

ENDPOINT = "https://api.indexnow.org/IndexNow"
KEY_RE = re.compile(r"^[A-Za-z0-9-]{8,128}$")


def find_key(root: Path):
    """Return (key, filename) from the single key file at the site root."""
    hits = []
    for f in sorted(root.glob("*.txt")):
        try:
            body = f.read_text(encoding="utf-8").strip()
        except (UnicodeDecodeError, OSError):
            continue
        if KEY_RE.match(body) and f.stem == body:
            hits.append((body, f.name))
    if not hits:
        sys.exit(
            f"No IndexNow key file in {root}.\n"
            "Expected <key>.txt at the site root whose contents equal its own name."
        )
    if len(hits) > 1:
        sys.exit(f"Multiple key files found: {[h[1] for h in hits]}. Keep exactly one.")
    return hits[0]


def read_sitemap(root: Path):
    path = root / "sitemap.xml"
    if not path.exists():
        sys.exit(f"No sitemap.xml in {root}.")
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    tree = ET.parse(path)
    urls = [
        el.text.strip()
        for el in tree.getroot().findall(".//s:loc", ns)
        if el.text and el.text.strip()
    ]
    if not urls:
        sys.exit("sitemap.xml parsed but contained no <loc> entries.")
    return urls


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    root = Path(sys.argv[1]).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"Not a directory: {root}")

    key, key_file = find_key(root)
    urls = read_sitemap(root)

    hosts = {urlparse(u).netloc for u in urls}
    if len(hosts) != 1:
        sys.exit(f"sitemap.xml mixes hosts {sorted(hosts)}. IndexNow needs exactly one.")
    host = hosts.pop()

    payload = {
        "host": host,
        "key": key,
        "keyLocation": f"https://{host}/{key_file}",
        "urlList": urls,
    }

    print(f"host        {host}")
    print(f"key file    {key_file}")
    print(f"urls        {len(urls)}")

    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.status
            body = resp.read().decode("utf-8", "replace").strip()
    except urllib.error.HTTPError as e:
        code = e.code
        body = e.read().decode("utf-8", "replace").strip()
    except urllib.error.URLError as e:
        sys.exit(f"Could not reach IndexNow: {e.reason}")

    hint = {
        200: "accepted",
        202: "accepted, key validation pending",
        400: "malformed request",
        403: "key file could not be read at keyLocation",
        422: "a URL did not match the registered host",
        429: "rate limited, try later",
    }.get(code, "")
    print(f"response    {code} {hint}")
    if body:
        print(f"body        {body}")
    sys.exit(0 if code in (200, 202) else 1)


if __name__ == "__main__":
    main()
