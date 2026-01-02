from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def fetch_url_text(url: str, timeout: int = 20) -> tuple[str, str]:
    """Return (final_url, cleaned_text)"""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; OutreachApp/0.1; +local)"
    }
    resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    html = resp.text

    soup = BeautifulSoup(html, "html.parser")
    # remove scripts/styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n")
    # normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return resp.url, text.strip()


def guess_key_pages(website: str) -> list[str]:
    """Return likely URLs for About/CSR/Partnership/Contact pages."""
    website = website.strip()
    if not website:
        return []
    if not website.startswith("http"):
        website = "https://" + website

    base = website.rstrip("/")
    candidates = [
        base,
        base + "/about",
        base + "/about-us",
        base + "/company",
        base + "/sustainability",
        base + "/csr",
        base + "/esg",
        base + "/community",
        base + "/foundation",
        base + "/partnership",
        base + "/partnerships",
        base + "/sponsorship",
        base + "/contact",
        base + "/contact-us",
    ]
    # ensure same host
    host = urlparse(base).netloc
    out = []
    for u in candidates:
        if urlparse(u).netloc == host:
            out.append(u)
    # remove duplicates while preserving order
    seen = set()
    dedup = []
    for u in out:
        if u not in seen:
            seen.add(u)
            dedup.append(u)
    return dedup
