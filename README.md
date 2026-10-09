# Review QR automation

Google review stands for restaurants, cafés, salons, gyms and other walk-in businesses, plus the system that finds
the customers. It starts with the US and other English-speaking markets.

- **Finds the businesses.**
  - It works through 30 US cities, a few at a time, on your own computer ([docs/LOCAL.md](docs/LOCAL.md)).
  - It covers 15 business types: restaurants, cafés, bars, bakeries, salons and barbers, gyms, hotels,
    dentists, garages and car washes, clinics and med spas, pet groomers and vets, tattoo studios, entertainment
    venues, boutiques and florists, and laundromats.
  - It uses open data (Overture Maps) and the businesses' own websites.
  - Only businesses you can write to go into the Google Sheet: those with an **e-mail address** or a
    **WhatsApp number**, each with evidence.
- **Contacts them.**
  - US: e-mails that follow CAN-SPAM, sent from your Gmail, warmed up slowly, with replies sorted for you.
  - Everywhere: a WhatsApp queue for businesses that publish a WhatsApp number.
  - Every message offers a free preview of the business's own page.
  - Rules for other markets are prepared: Canada, the UK, Ireland, Australia, New Zealand, UAE, Singapore
    (and Germany).
- **Runs the product.**
  - A small page per customer behind QR/NFC stands, with *Pay the bill* and *Write a Google review* side by side.
    The guest comes back to the pay button after reviewing.
  - WhatsApp review requests to guests who agreed.
  - Everything inside Google's review rules.

| Read | For |
|---|---|
| [docs/SETUP.md](docs/SETUP.md) | **start here**: step-by-step setup for beginners (Gmail, Sheet, keys, Cloudflare) |
| [docs/LOCAL.md](docs/LOCAL.md) | running the lead search and the e-mails on your own computer (double-click `run_*.bat`) |
| [docs/OUTREACH.md](docs/OUTREACH.md) | e-mails and WhatsApp: your daily routine |
| [docs/BUSINESS.md](docs/BUSINESS.md) | the product, prices, competitors, who to sell to |
| [docs/COMPLIANCE.md](docs/COMPLIANCE.md) | the rules per country, with sources |
| [docs/CUSTOMERS.md](docs/CUSTOMERS.md) | setting up a customer: page, QR/NFC stands, guest messages |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | how it works inside |

## Folders

```
leadgen/            lead engine + outreach (python -m leadgen ...)
  country.py        country packs: words, domains, postcodes, contact rules
  outreach/         e-mails, WhatsApp queue, replies (letters where e-mail needs consent)
config/us/          one file per US city, _base.toml (shared), fleet.toml (which cities run), outreach.toml
config/shared/      the business types (categories.toml)
config/examples/    single campaigns: UK, Australia, ...
site/               customer pages: site.json (you), businesses/<id>.json (customers), build.py
marketing/          the two-page sales PDF for businesses (pitch.json = your details, build_pitch.py)
guests/             WhatsApp review requests to guests who agreed
scripts/            make_us_cities.py (city files), ci/ (fleet plan, encrypted state, probes)
.github/workflows/  US fleet, outreach, tests, probes
```

## Run locally

Day to day: `run_leads.bat`, `run_emails.bat` and `run_check.bat` (Windows) or the `.sh` files (Mac), set up as in
[docs/LOCAL.md](docs/LOCAL.md). For development:

```
pip install -r requirements.txt -r site/requirements.txt pytest
python -m pytest -q                                   # all tests, offline
python -m leadgen doctor --config config/us/austin.toml
python site/build.py --preview                        # the customer pages -> site/public/
python -m guests.review_requests demo-cafe guests.csv # one-tap WhatsApp page for a guest list
```

Lead data, guest lists and keys never go into git (`.gitignore`: `.env`, `secrets/`, `data/`).

## For website owners: ReviewLeadBot

If you found this page through your server logs: `ReviewLeadBot` reads the public contact pages of local
businesses (home, contact, about, privacy pages, at most ten pages per site). It identifies itself and
follows your `robots.txt`. When a site does not answer, it reads that site's copy in Common Crawl's public
archive instead. To keep it out, add:

```
User-agent: ReviewLeadBot
Disallow: /
```

To have your business's details removed, open an issue in this repository or reply "delete" to any e-mail
from us. We erase them and never contact you again.
