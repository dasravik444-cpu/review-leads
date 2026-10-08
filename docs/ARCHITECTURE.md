# Architecture

Three parts, one repository:

| Part | Folder | Runs on | Does |
|---|---|---|---|
| Lead engine | `leadgen/` | GitHub Actions (daily) | finds review-sensitive businesses in a campaign area, with evidence for every contact |
| Outreach | `leadgen/outreach/` | GitHub Actions (weekdays) | letters, e-mails and a WhatsApp queue, following each country's rules |
| Customer pages | `site/` | Cloudflare Workers (static files) | one pay/review page per customer behind the QR/NFC stands, the preview page, legal pages |
| Guest requests | `guests/` | the restaurant's laptop or ours | WhatsApp review requests to guests who agreed |

## Many cities at once: the US fleet

```
config/us/fleet.toml ──► job "plan" ──► one job per city, in parallel (public repo: up to 15 at a time)
                          (visibility,      │  restore rq-state-us-<city> (encrypted)
                           budget, cities)  │  find + enrich businesses (open data + own websites)
                                            │  e-mail hunt
                                            │  sync to the shared Google Sheet
                                            │  save rq-state-us-<city>
                                            ▼
                         Google Sheet:  "Leads" (all cities, Lead ID prefix per city)
                                        "Daily Report" (one row per city per run, Campaign column)
                                            ▼
                         workflow "Outreach" (config/us/outreach.toml): one Gmail, reads "Leads"
```

- **Cities stay independent.** Each city is an ordinary campaign: its own plan, its own memory and its own lead
  numbers. One city failing never stops the others (`fail-fast: false`). The circles never overlap, so a business
  belongs to exactly one city.
- **The Sheet is safe to share:**
  - New rows are appended. Changed rows are updated by their own row number, read fresh before each write.
  - Only the Key and Lead ID columns are read to find them.
  - A tab that another city's run created at the same moment is accepted.
  - The Plan tab is switched off (`plan_tab = ""`). The Daily Report starts with a Campaign column.
- **Only reachable leads go into the Sheet** (`[sheets] require_any = ["email", "whatsapp"]`). Phone-only
  businesses stay in the city's memory. The e-mail hunt keeps looking at them, and they join the Sheet once an
  e-mail is found.
- **Why no LLM "agents".** The work is checking public data for exact facts (an e-mail on a business's own
  website), which plain code does faster, for free and without inventing anything. LLM calls would cost money per
  business and could invent contacts. The pipeline is still made of specialised workers (the table below); the
  "multi-agent" part that makes it fast is running many of them in parallel, one per city.

## Principles

1. **Evidence or nothing.** A contact is stored only if it was read literally from a public source. Each contact
   row keeps `source`, `source_url`, `confidence`, `evidence` and every corroborating source. No LLM touches the
   data.
2. **Durable, isolated tasks.** All work is rows in SQLite (`tasks`). A task's result and the follow-up tasks it
   creates are committed in one transaction. A failure is recorded on that task (with back-off) and never stops
   other tasks.
3. **Bounded waits.** HTTP requests retry at most once with short waits. Every request has a timeout and a size
   cap, and the run has a deadline.
4. **Degrade, don't die.** If the open data cannot be read, the stored extract or OpenStreetMap answers instead.
   Work that cannot be done now is deferred without burning retries.
5. **Calendar, not counters.** Which part of the area is scheduled for a day is derived from the start date, so
   re-runs and missed days never skip territory.
6. **Always report.** Every run ends with a Sheets sync and a report, even when cut short. Important failures
   make the run exit non-zero, and GitHub e-mails you.
7. **E-mails: observed, or clearly flagged.** The *Emails* column holds only addresses read from a public
   source. `info@`/`kontakt@` candidates (MX-checked) for a business with its own website go in the *unverified*
   column, labelled as guessed. They are never used where only published addresses may be e-mailed (Australia).
8. **The country decides.** Contact rules, language, domains, postcodes and page names come from the campaign's
   country pack (`leadgen/country.py`), not from code paths.

## Agents

| Agent | Module | Input → output |
|---|---|---|
| Country pack | `country.py` | campaign country → words, domains, postcodes, contact pages, contact rules |
| Planner | `planner.py`, `geo.py`, `providers/osm.py` | config → parts, search squares, `search` tasks |
| Discovery | `providers/overture.py` (default), `osm.py`; `gmaps.py`, `places_api.py` (standard mode only) | square + category → places |
| Quality | `quality.py`, `runner._ingest` | places → kept / excluded (closed, chain, off-category, duplicate, outside area, excluded name) |
| Website | `enrich/website.py`, `enrich/extract.py` | the business's own site → e-mails, phones, WhatsApp, social links, owner name, legal form, "no advertising" notice, description, USP |
| E-mail hunt | `hunt.py`, `enrich/domains.py`, `enrich/emails.py` | leads without e-mail → deeper look at their site, a site the listing lacks |
| Recorder | `sheets.py`, `report.py` | database → Leads / Plan / Daily Report tabs |
| Observer | `runner._summary`, `report.py` | run → JSON report, job summary, warnings, exit code |
| Orchestrator | `runner.py` | the loop with the time budget and the stopping rule |
| Outreach | `outreach/engine.py` + `templates.py`, `mailer.py`, `inbox.py`, `classify.py`, `sheet.py` | Leads tab → letters, e-mails, WhatsApp queue, replies, Do Not Contact |
| Pages | `site/build.py`, `site/assets/` | `site/businesses/*.json` → static pages, QR codes, legal pages |
| Guest requests | `guests/review_requests.py` | guest CSV → one-tap WhatsApp page or Cloud API messages |

## Daily loop

```
recover interrupted tasks -> ensure plan -> scheduled part for today
loop until deadline or stop signal:
    harvest finished enrichment results (DB writes happen only in the main thread)
    if new_leads_today < target  OR  searches of today's part (or earlier ones) remain:
        run the next search (plan order) -> ingest places -> queue enrichment
    keep up to 2 x workers enrichment tasks running in a thread pool
    every 20 minutes: copy new/changed lead rows to the sheet (checkpoint)
    stop when there is nothing left to do now
drain in-flight work (bounded), put unfinished tasks back in the queue
refresh part status -> Google Sheets upsert -> Plan tab -> Daily Report row -> JSON + summary
then: e-mail hunt for leads still without an e-mail (45 minutes in the US fleet)
```

Enrichment per business (open-data mode):

```
open data: phones, e-mails, website, social links (with the record id as evidence)
website?  yes -> crawl as ReviewLeadBot, robots.txt respected: home page + up to 5 contact pages
                 (Kontakt, Impressum, Über uns, Contact, About...), privacy pages and the sitemap's contact pages
          no  -> the e-mail hunt tries the obvious domains for the name; a site counts only if it shows
                 the business's phone number, or its name with its postcode
site does not answer -> its archived pages from Common Crawl, read with the same rules
still no e-mail      -> web search for the address it published elsewhere ([enrich] email_search), kept only
                        when tied to the business (its domain or name, or its phone number shown with it)
```

A business becomes a **lead** when it has at least one phone, WhatsApp, e-mail or Instagram that is not
low-confidence. Low-confidence findings go to *Other Contacts (unverified)*.

## Country packs

`leadgen/country.py` holds one `Pack` per country: DE, US, GB, AU, and IN for the engine's original tests.
Each pack has:

- **Language and words:** language and Accept-Language; descriptive words that do not identify a business
  (*Restaurant*, *Bäckerei*, *GmbH*...); the country's big cities.
- **Web details:** domain endings (`.de`, `.com`, `.berlin`...); the postcode pattern; contact and policy page
  names (`/kontakt`, `/impressum`, `/datenschutz`...).
- **Rules:** `cold_email`, `cold_whatsapp`, `postal_address_required`, `privacy_notice` and `letters`. They come
  from docs/COMPLIANCE.md.

The campaign's `country` selects the pack when the config is loaded (`config.activate`).

Two columns of the Leads tab come from the website and the pack:

- **Legal Form:** GmbH/UG/AG, Ltd/LLP/PLC, Pty Ltd, LLC/Inc, sole trader or partnership. It is read from the
  Impressum or footer, with the sentence as evidence.
- **Contact Rule:** how this lead may be contacted here, e.g. "Letter only (no cold e-mail/WhatsApp - UWG §7);
  e-mail once they ask".

To add a country:

1. Research its rules and add a section to docs/COMPLIANCE.md.
2. Add a `Pack` with its words, domains, postcode pattern and pages.
3. Add a test in `tests/test_countries.py`.
4. Add an example config.

## Accuracy rules

- **Names match word by word.** Every distinctive word of the business name must appear (in the profile name, or
  at word boundaries in a handle or domain). Spelling variants may differ only in vowels, doubled letters or
  umlauts (*Müller*/*Mueller*), not in consonants.
- **Common words need local proof.** If the only matching word is a common word, the page must mention the
  city or a postcode of the area. Otherwise the find is stored as unverified.
- **The site must belong to the business.** If neither the business name nor its phone appears on a site (a
  parent company, a listing site), its contacts are unverified and its description is not used.
- **Impressum names.** An owner or manager is taken only from an explicit line ("Inhaber: …",
  "Geschäftsführer: …", "Owner: …"). A street name glued to the name is cut off. Words like "Ihre Daten" are not
  names.
- **Agencies are not the business.** Lines such as "Webdesign: …" or "Realisiert von …" are dropped with their
  phone and e-mail.
- **Placeholders are junk.** `max@mustermann.de`, `name@domain.com` and listing or booking sites'
  addresses are never stored.

## Open-data mode (default)

`[compliance] mode = "open-data"` limits the system to sources whose licences allow storing and re-using the
data, plus the businesses' own websites:

- **Overture Maps places.** These are open data (CDLA-Permissive-2.0 / Apache-2.0), drawn from Meta, Microsoft,
  Foursquare and others. `providers/overture.py` reads only the campaign's bounding box and the configured
  category codes (`overture = [...]` per category; codes or `basic_category`, `*` patterns allowed) with DuckDB,
  straight from the public S3 bucket. It stores them in `open_places`, refreshed monthly.
- **Websites** are crawled as `ReviewLeadBot/2.0` (set `[crawler] contact_url` once you have a page saying who
  crawls). Requests use no browser impersonation, and robots.txt is evaluated for that bot name.
- Google Maps, search engines and Instagram are not used. `hybrid` and `standard` modes exist in the code but
  are off.

Measured 2026-10-08 for 20 km around Berlin: 38,572 businesses in the review categories (restaurants 16,318,
salons 8,458, cafés 4,523, bars 3,729, gyms 2,835, bakeries 2,709). About 80% have a phone and 25% an e-mail
(*Actions → Open data coverage probe*).

## Search squares and parts

- Business density from OpenStreetMap drives a quadtree. A square splits while it holds more than 60 mapped
  businesses (down to 1 km), and always splits above 8 km.
- Squares are ordered along a Hilbert curve and cut into N daily groups of equal expected yield. The groups go
  from the centre outwards and are named after their main localities.

## State

- **Lead state:** `state/leadgen.sqlite` holds `parts`, `cells`, `tasks`, `places`, `open_places`, `contacts`,
  `runs`, `budget`, `events` and `meta`.
- **Outreach state:** `outreach-state/outreach.sqlite` holds `threads`, `sends`, `replies`, `suppression`,
  `wa`, `letters` and `meta`.
- **Between runs on GitHub Actions:** each is restored before the run and saved after it as an AES-256 encrypted
  artifact (`scripts/ci/state.sh`). The artifacts are named `rq-state-<campaign id>` and
  `rq-outreach-<campaign id>`, kept 30 days, with only the newest 3 kept (private repositories get 500 MB of
  artifact storage).
- **When a restore fails:** if listing, download, decryption or the integrity check fails, the run stops and
  nothing is saved. A good state is never replaced by a broken one.
- **If the state is lost:** sheet rows are matched by key, so a fresh database updates existing rows and adopts
  their Lead IDs.

## Leads tab columns

`Lead ID, Date Added, Business Name, Category, Area, Address, Phones, WhatsApp, Emails, Instagram, Facebook,
LinkedIn, Contact Person, Website, Google Maps, Rating, Priority, Signals, USP, Legal Form, Contact Rule,
Description, Contact Sources, Other Contacts (unverified), Plan Part, Last Updated, Key, Status`.

- The system writes *Status* only for new rows and for its own outreach statuses. Anything you type there means
  hands off.
- *Google Maps* is a search link for a person to open. No Google data is fetched.
- A sheet with an older column layout is upgraded in place.

## Customer pages (`site/`)

`python site/build.py` turns `site/site.json` (you) and `site/businesses/*.json` (customers) into `site/public/`:

- `r/<id>/index.html`, `de.html`, `en.html`: the pay/review page. `r.js` notices when the guest comes back from
  Google (visibility, focus and back-forward-cache events) and points to the pay button.
- `r/<id>/thanks*.html`: the page that Stripe and Square send guests to after paying.
- `r/<id>/qr.svg`: the QR code for the stands.
- `demo/`: the preview for letters and e-mails (`?n=<business>&lang=de|en`). The name is only ever set as text.
- `impressum.html`, `datenschutz.html`, `legal.html`, `privacy.html`, `_headers` (strict CSP, nothing inline)
  and `robots.txt`.
- The build refuses review and payment links outside the known providers' hosts, ids that would break printed
  QR codes, and `FILL_IN` left in `site.json` (except with `--preview`).

## Guest requests (`guests/`)

`python -m guests.review_requests <id> guests.csv [--send]` follows the rules in docs/COMPLIANCE.md, section 5:

- Only guests who consented are asked, 2 hours to 7 days after the visit.
- Each guest gets one request in 90 days plus at most 3 short reminders (days 2, 5 and 9), never after STOP or
  once they have reviewed.
- Everyone gets the same neutral text.

The memory is a small JSON file per customer (`guests-state/`). Both it and the output pages are kept out of git.
