"""
Internship page monitor.

Fetches each career/opportunity page in TARGETS, hashes its visible text,
and compares against the hash saved last time (state.json, committed back
to the repo by the GitHub Actions workflow). If a page's content changed,
it emails you.

This is a "something changed" detector, not a "they're hiring" detector —
some changes will be noise (a banner, a date stamp). That's a reasonable
trade-off for a free, zero-maintenance checker: an occasional false-positive
email beats missing the real one.
"""

import hashlib
import json
import os
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup

STATE_FILE = Path(__file__).parent / "state.json"

# id must be stable — it's the key used to track each page's last-seen hash.
TARGETS = [
    {"id": "msexplore", "company": "Microsoft", "program": "Explore Internship", "url": "https://apply.careers.microsoft.com/careers"},
    {"id": "cisco", "company": "Cisco", "program": "Ideathon", "url": "https://careers.cisco.com/global/en/india/etr/ideathon"},
    {"id": "flipkart", "company": "Flipkart", "program": "GRID", "url": "https://dsa.apnacollege.in/flipkart"},
    {"id": "jpmorgan", "company": "JP Morgan", "program": "Code for Good", "url": "https://www.jpmorganchase.com/careers/explore-opportunities/programs/tfsg-hackathons"},
    {"id": "infosys", "company": "Infosys", "program": "InStep", "url": "https://www.infosys.com/instep.html"},
    {"id": "googlestep", "company": "Google", "program": "STEP Internship", "url": "https://www.google.com/about/careers/applications/internships"},
    {"id": "accenture", "company": "Accenture", "program": "Tech Next Challenge", "url": "https://technextchallenge.in/"},
    {"id": "goldman", "company": "Goldman Sachs", "program": "India Hackathon", "url": "https://www.goldmansachs.com/careers/programs-and-internships"},
    {"id": "sih", "company": "Govt. of India", "program": "Smart India Hackathon", "url": "https://www.sih.gov.in/"},
    {"id": "imaginecup", "company": "Microsoft", "program": "Imagine Cup", "url": "https://imaginecup.microsoft.com/en-us"},
    {"id": "metahackercup", "company": "Meta", "program": "Hacker Cup", "url": "https://www.facebook.com/codingcompetitions/hacker-cup/"},
    {"id": "amazonintern", "company": "Amazon", "program": "Internship", "url": "https://www.amazon.jobs/content/en/career-programs/university/internships-for-students"},
    {"id": "gsoc", "company": "Google", "program": "Summer of Code", "url": "https://summerofcode.withgoogle.com/"},
    {"id": "msresearch", "company": "Microsoft", "program": "Research", "url": "https://www.microsoft.com/en-us/research/"},
    {"id": "tcsresearch", "company": "TCS", "program": "Research Internship", "url": "https://www.tcs.com/careers/india/internship"},
    {"id": "pmis", "company": "Govt. of India", "program": "PM Internship Scheme", "url": "https://pminternship.mca.gov.in/login/"},
    {"id": "isro", "company": "ISRO", "program": "Student Project Training", "url": "https://www.isro.gov.in/InternshipAndProjects.html"},
    {"id": "5ghackathon", "company": "Dept. of Telecom", "program": "5G Innovation Hackathon", "url": "https://eservices.dot.gov.in/5ghackathon/"},
    {"id": "digitalindia", "company": "Govt. of India", "program": "Digital India Internship", "url": "https://dii.nic.in/"},
    # DRDO, MLH (closed to India/APAC), and Juspay/HackOn (unofficial-source links)
    # were left out — add them back in once you have a stable official URL for each.
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def fetch_text(url: str) -> str | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ! fetch failed: {e}")
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())
    return text


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
        new_hash = hash_text(text)
        old_hash = state.get(target["id"])
        if old_hash is not None and old_hash != new_hash:
            print("  -> CHANGED")
            changed.append(target)
        state[target["id"]] = new_hash

    save_state(state)

    if changed:
        send_email(changed)
        print(f"Emailed about {len(changed)} change(s).")
    else:
        print("No changes detected.")


if __name__ == "__main__":
    sys.exit(main())
