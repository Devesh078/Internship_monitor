# Internship Radar — email alerts

Checks 19 career/opportunity pages once a day (free, via GitHub Actions) and
emails you when a page's content changes. Runs entirely on GitHub's
infrastructure — nothing needs to stay open on your laptop or phone.

## How it works

1. Each day, GitHub runs `check_internships.py`.
2. It downloads each page in `TARGETS`, strips scripts/styles, and hashes
   the visible text.
3. It compares that hash to the one saved last time (`state.json`).
4. If any page's hash changed, it emails you a list of what changed.
5. It commits the new hashes back to the repo so tomorrow's run has
   something to compare against.

The first run just records a baseline for every page (nothing to compare
yet), so you won't get an email on day one — only from day two onward, when
something actually differs from day one.

## Setup (10 minutes, all free)

1. **Create a new GitHub repo** and push everything in this folder to it
   (including the hidden `.github` folder).

2. **Get a Gmail App Password** (don't use your real Gmail password):
   - Turn on 2-Step Verification on your Google account if it isn't already.
   - Go to https://myaccount.google.com/apppasswords
   - Create an app password (name it anything, e.g. "internship radar").
   - Copy the 16-character password it gives you.

   (Using a different email provider is fine too — just change the
   `smtp.gmail.com` / port 465 line in `check_internships.py` to match
   your provider's SMTP settings.)

3. **Add three repo secrets** — in your GitHub repo, go to
   `Settings → Secrets and variables → Actions → New repository secret`:
   - `EMAIL_ADDRESS` — the Gmail address you made the app password for
   - `EMAIL_PASSWORD` — the 16-character app password from step 2
   - `RECIPIENT_EMAIL` — where you want alerts sent (can be the same address)

4. **Trigger it once manually** to check it works: go to the
   `Actions` tab → `Check internship pages` → `Run workflow`. Check the run
   log — you should see "No changes detected" (since it has nothing to
   compare against yet) and `state.json` should get committed.

5. From then on, it runs automatically every day at 10:30 AM IST. Change the
   `cron` line in `.github/workflows/check.yml` if you want a different time.

## Adding or editing targets

Open `check_internships.py` and edit the `TARGETS` list — each entry needs
a stable `id`, a `company`, a `program` name, and the `url` to check. A few
were left out on purpose (see the comment in the file) because their only
known link was an unofficial blog rather than the company's own page —
add them back once you find a reliable official URL.

## Honest limitations

- This detects *page changes*, not *new hiring specifically* — a redesigned
  banner or a date stamp updating can trigger a false-positive email. That's
  the trade-off for something free and zero-maintenance; treat each alert as
  "go check the page," not gospel.
- Pages that render their content entirely via JavaScript (rare among these,
  but possible) may not show real content to a simple `requests` fetch. If a
  particular company never seems to trigger, that's the likely reason —
  flag it and it can be upgraded to a headless-browser fetch instead.
- Government sites occasionally rate-limit or block automated requests; if
  one keeps failing in the Actions log, that's usually why.
