"""
Internship page monitor.

Fetches each career/opportunity page in TARGETS, cleans its visible text,
and compares it against the text saved last time (state.json, committed
back to the repo by the GitHub Actions workflow). If a page's content
changed by more than a small threshold, it emails you.

This is a "something changed" detector, not a "they're hiring" detector —
it compares how much of each page's text actually differs from last time,
ignoring small amounts of drift (a rotating banner, a session token) so it
only emails you when a meaningful chunk of the page has changed.
"""

import json
import os
import re
import smtplib
import sys
from difflib import SequenceMatcher
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup

STATE_FILE = Path(__file__).parent / "state.json"

# Below this similarity ratio (0-1), a page counts as "changed enough to
# email about". 0.97 means more than ~3% of the text differs. Lower this
# if you're missing real changes; raise it if you're still getting noise.
SIMILARITY_THRESHOLD = 0.97

# Cap how much text we store per page, to keep state.json a sane size.
MAX_STORED_CHARS = 20000

# id must be stable — it's the key used to track each page's last-seen hash.
TARGETS = [
    {"id": "msexplore", "company": "Microsoft", "program": "Explore Internship", "url": "https://apply.careers.microsoft.com/careers"},
    {"id": "cisco", "company": "Cisco", "program": "Ideathon", "url": "https://careers.cisco.com/global/en/india/etr/ideathon"},
    {"id": "flipkart", "company": "Flipkart", "program": "GRID", "url": "https://dsa.apnacollege.in/flipkart"},
    {"id": "jpmorgan", "company": "JP Morgan", "program": "Code for Good", "url": "https://www.jpmorganchase.com/careers/explore-opportunities/programs/tfsg-hackathons"},
    {"id": "infosys", "company": "Infosys", "program": "InStep", "url": "https://www.infosys.com/instep.html"},
    {"id": "googlestep", "company": "Google", "program": "STEP Internship", "url": "https://www.google.com/about/careers/applications/internships"},
    {"id": "accenture", "company": "Accenture", "program": "Tech Next Challenge", "url": "https://technextchallenge.in/"},
    {"id": "goldman", "company": "Goldman Sachs", "program": "India Hackathon", "url": "https://www.goldmansachs.com/careers/students/programs-and-internships/india/hackathon"},
    {"id": "sih", "company": "Govt. of India", "program": "Smart India Hackathon", "url": "https://www.sih.gov.in/"},
    {"id": "imaginecup", "company": "Microsoft", "program": "Imagine Cup", "url": "https://imaginecup.microsoft.com/en-us"},
    # Meta Hacker Cup dropped: facebook.com blocks almost all non-browser
    # requests outright (400s), so a simple checker will never read it reliably.
    {"id": "amazonintern", "company": "Amazon", "program": "Internship", "url": "https://www.amazon.jobs/content/en/career-programs/university/internships-for-students"},
    {"id": "gsoc", "company": "Google", "program": "Summer of Code", "url": "https://summerofcode.withgoogle.com/"},
    {"id": "msresearch", "company": "Microsoft", "program": "Research", "url": "https://www.microsoft.com/en-us/research/"},
    {"id": "tcsresearch", "company": "TCS", "program": "Research Internship", "url": "https://www.tcs.com/careers/india/internship"},
    {"id": "pmis", "company": "Govt. of India", "program": "PM Internship Scheme", "url": "https://pminternship.mca.gov.in/"},
    {"id": "isro", "company": "ISRO", "program": "Student Project Training", "url": "https://www.isro.gov.in/InternshipAndProjects.html"},
    {"id": "5ghackathon", "company": "Dept. of Telecom", "program": "5G Innovation Hackathon", "url": "https://eservices.dot.gov.in/5ghackathon/"},
    {"id": "digitalindia", "company": "Govt. of India", "program": "Digital India Internship", "url": "https://dii.nic.in/"},
    # DRDO, MLH (closed to India/APAC), and Juspay/HackOn (unofficial-source links)
    # were left out — add them back in once you have a stable official URL for each.
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_text(url: str) -> str | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ! fetch failed: {e}")
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())
    return normalize(text)


def normalize(text: str) -> str:
    """Strip tokens that regenerate on every load regardless of real
    content changes: long hex/alphanumeric IDs (session tokens, CSRF
    nonces, cache-busting hashes) and long numeric strings."""
    text = re.sub(r"\b[a-fA-F0-9]{16,}\b", "", text)
    text = re.sub(r"\b[A-Za-z0-9_-]{24,}\b", "", text)
    text = re.sub(r"\b\d{6,}\b", "", text)
    return " ".join(text.split())[:MAX_STORED_CHARS]


def similarity(old: str, new: str) -> float:
    if not old:
        return 1.0
    return SequenceMatcher(None, old, new).ratio()


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def send_email(changed: list[dict]) -> None:
    sender = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]
    # RECIPIENT_EMAIL can be one address or several, comma-separated,
    # e.g. "a@gmail.com, b@gmail.com, c@gmail.com"
    raw_recipients = os.environ.get("RECIPIENT_EMAIL", sender)
    recipients = [addr.strip() for addr in raw_recipients.split(",") if addr.strip()]

    lines = ["The following internship/opportunity pages changed:\n"]
    for item in changed:
        lines.append(f"- {item['company']} — {item['program']}\n  {item['url']}\n")
    lines.append("\n(Automated check — verify on the page itself before acting.)")

    msg = MIMEText("\n".join(lines))
    msg["Subject"] = f"[Internship Radar] {len(changed)} page(s) changed"
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipients, msg.as_string())


def main():
    state = load_state()
    changed = []

    for target in TARGETS:
        print(f"Checking {target['company']} — {target['program']}")
        text = fetch_text(target["url"])
        if text is None:
            continue
        old_text = state.get(target["id"])
        if old_text is not None:
            ratio = similarity(old_text, text)
            if ratio < SIMILARITY_THRESHOLD:
                print(f"  -> CHANGED ({ratio:.1%} similar)")
                changed.append(target)
            else:
                print(f"  ok ({ratio:.1%} similar)")
        state[target["id"]] = text

    save_state(state)

    if changed:
        send_email(changed)
        print(f"Emailed about {len(changed)} change(s).")
    else:
        print("No changes detected.")


if __name__ == "__main__":
    sys.exit(main())
