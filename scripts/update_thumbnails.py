#!/usr/bin/env python3
"""
Scrape the og:image URL from each EoH Arma Reforger Workshop page linked in
mods.html, and rewrite the matching <div class="mod-thumb"> background-image
URLs in place. Idempotent — only writes if something actually changed.

Run manually:  python scripts/update_thumbnails.py
Or via the daily GitHub Actions workflow: .github/workflows/update-mod-thumbnails.yml
"""
import re
import sys
import urllib.request
from pathlib import Path

MODS_HTML = Path(__file__).resolve().parent.parent / "mods.html"

# Regex helpers
WORKSHOP_LINK_RE = re.compile(
    r'href="(https://reforger\.armaplatform\.com/workshop/([^"]+))"\s+target="_blank"\s+rel="noopener"\s+class="mod-thumb-link"'
)
THUMB_DIV_RE_TMPL = (
    r'(<a href="{url}" target="_blank" rel="noopener" class="mod-thumb-link">'
    r'<div class="mod-thumb" style="background-image:url\()'
    r'[^)]+'
    r'(\);"></div></a>)'
)
OG_IMAGE_RE = re.compile(rb'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.IGNORECASE)
# Fallback ordering — some pages put content before property
OG_IMAGE_RE_ALT = re.compile(rb'<meta[^>]+content="([^"]+)"[^>]+property="og:image"', re.IGNORECASE)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (EoH thumbnail updater)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def find_og_image(html: bytes) -> str | None:
    m = OG_IMAGE_RE.search(html) or OG_IMAGE_RE_ALT.search(html)
    return m.group(1).decode("utf-8") if m else None


def main() -> int:
    if not MODS_HTML.exists():
        print(f"mods.html not found at {MODS_HTML}", file=sys.stderr)
        return 1

    text = MODS_HTML.read_text(encoding="utf-8")
    workshop_urls = WORKSHOP_LINK_RE.findall(text)
    if not workshop_urls:
        print("No workshop mod links found in mods.html — nothing to update.")
        return 0

    print(f"Found {len(workshop_urls)} mod thumbnails to check.")
    updated = 0
    failed = 0

    for url, mod_id in workshop_urls:
        try:
            html = fetch(url)
            og_image = find_og_image(html)
            if not og_image:
                print(f"  [WARN] {mod_id}: og:image not found, skipping")
                failed += 1
                continue
        except Exception as e:
            print(f"  [WARN] {mod_id}: fetch failed ({e}), skipping")
            failed += 1
            continue

        # Replace this card's thumbnail URL
        pattern = re.compile(THUMB_DIV_RE_TMPL.format(url=re.escape(url)))
        new_text, n = pattern.subn(rf"\g<1>{og_image}\g<2>", text)
        if n == 0:
            print(f"  [WARN] {mod_id}: no matching thumb div found")
            failed += 1
            continue

        if new_text != text:
            updated += 1
            print(f"  [UPDATED] {mod_id} -> {og_image}")
        text = new_text

    if updated:
        MODS_HTML.write_text(text, encoding="utf-8")
        print(f"\nWrote {updated} thumbnail update(s) to mods.html.")
    else:
        print("\nAll thumbnails already up to date.")

    if failed:
        print(f"({failed} mod(s) could not be checked — see warnings above.)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
