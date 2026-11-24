"""
Bulk Email Finder
-----------------
Use:
  1. pip install requests dnspython
  2. sites.txt me domains likho (ek line me ek)
  3. python email_finder.py
  4. results.csv me output milega
"""
import csv
import re
import sys
import concurrent.futures as cf

import requests

try:
    import dns.resolver
except ImportError:
    dns = None

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
PATHS = [
    "", "/contact", "/contact-us", "/contact-us/", "/contact.html", "/about",
    "/about-us", "/write-for-us", "/guest-post", "/submit-guest-post",
    "/advertise", "/work-with-us", "/privacy-policy",
]
GUESS_PREFIXES = ["info", "contact", "editor", "hello", "admin", "support", "team"]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9\-]+(?:\.[a-zA-Z0-9\-]+)*\.[a-zA-Z]{2,}")
CF_RE = re.compile(r'data-cfemail="([0-9a-fA-F]+)"')
FB_RE = re.compile(r'https?://(?:www\.)?facebook\.com/(?!sharer|share|tr\?|plugins|dialog)[A-Za-z0-9_.\-/]+')
LI_RE = re.compile(r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:company|in|school)/[A-Za-z0-9_.\-%]+')
BAD_END = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js", ".woff", ".woff2")


def clean_domain(raw):
    d = raw.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    return d.split("/")[0]


def decode_cf(hexstr):
    key = int(hexstr[:2], 16)
    return "".join(chr(int(hexstr[i:i + 2], 16) ^ key) for i in range(2, len(hexstr), 2))


def deobfuscate(text):
    text = re.sub(r"\s*[\[\(\{]\s*at\s*[\]\)\}]\s*", "@", text, flags=re.I)
    text = re.sub(r"\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*", ".", text, flags=re.I)
    return text


def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if r.status_code == 200 and "text" in r.headers.get("Content-Type", "text"):
            return r.text
    except requests.RequestException:
        pass
    return ""


def has_mx(domain):
    if dns is None:
        return False
    try:
        return len(dns.resolver.resolve(domain, "MX", lifetime=5)) > 0
    except Exception:
        return False


def process(raw):
    domain = clean_domain(raw)
    emails, fbs, lis = set(), set(), set()
    reachable = False

    for path in PATHS:
        html = ""
        for scheme in ("https://", "http://"):
            html = fetch(f"{scheme}{domain}{path}")
            if html:
                break
        if not html:
            continue
        reachable = True

        for h in CF_RE.findall(html):
            try:
                emails.add(decode_cf(h).lower())
            except ValueError:
                pass
        for m in EMAIL_RE.findall(deobfuscate(html)):
            m = m.lower().strip(".")
            if not m.endswith(BAD_END):
                emails.add(m)
        fbs.update(u.rstrip("/") for u in FB_RE.findall(html))
        lis.update(u.rstrip("/") for u in LI_RE.findall(html))

        # same-domain email mil gaya to baqi pages ki zaroorat nahi (email ke liye)
        if any(e.endswith("@" + domain) for e in emails) and fbs and lis:
            break

    own = sorted(e for e in emails if e.endswith("@" + domain) or e.endswith("." + domain))
    other = sorted(e for e in emails if e not in own)

    status = "found" if own else ("found (other domain)" if other else "")
    guessed = ""
    if not own and not other:
        if has_mx(domain):
            guessed = ", ".join(f"{p}@{domain}" for p in GUESS_PREFIXES[:3])
            status = "guessed (not confirmed)"
        else:
            status = "site unreachable" if not reachable else "no email found"

    return {
        "site": domain,
        "status": status,
        "emails": ", ".join(own),
        "other_emails": ", ".join(other[:3]),
        "guessed_emails": guessed,
        "facebook": " | ".join(sorted(fbs)[:2]),
        "linkedin": " | ".join(sorted(lis)[:2]),
    }


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "sites.txt"
    with open(path, encoding="utf-8") as f:
        sites = [l.strip() for l in f if l.strip()]
    sites = list(dict.fromkeys(sites))
    print(f"{len(sites)} sites check ho rahi hain...")

    rows = []
    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        for i, row in enumerate(ex.map(process, sites), 1):
            rows.append(row)
            print(f"[{i}/{len(sites)}] {row['site']}: {row['status']} {row['emails']}")

    fields = ["site", "status", "emails", "other_emails", "guessed_emails", "facebook", "linkedin"]
    with open("results.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print("Done. results.csv ban gayi.")


if __name__ == "__main__":
    main()
