# Setup, step by step (beginner-friendly, about 1–2 hours once)

> **Update, 9 October 2026: the daily work runs on your own computer now ([LOCAL.md](LOCAL.md)).** GitHub's terms
> allow its free Actions computers only for building, testing and deploying the software, and GitHub blocked the
> account's Actions after the 30-city run. Steps 2–5 and 7 below (Gmail, Google key, Sheet, password, Cloudflare)
> still apply. Step 6 (keys in GitHub) and step 8 (runs on GitHub) are replaced by LOCAL.md. In GitHub, set the
> variables `FLEET_ENABLED` and `OUTREACH_ENABLED` to `false` (their timers are switched off in the code anyway).

Everything here is free. You need a computer with a browser and your phone (for Google's verification codes).
Do the steps in order. Each step says exactly where to click. Words in **bold** are buttons or menu items.

What you will create:

| # | What | Why |
|---|---|---|
| 1 | A **public** GitHub repository | the "robot" runs there for free (explained in step 1) |
| 2 | A new Gmail account | sends the e-mails to businesses and receives their replies |
| 3 | A Google Cloud "service account" | a robot login that may write into your Google Sheet |
| 4 | A Google Sheet | where all the leads appear |
| 5 | A secret password, `RQ_STATE_KEY` | locks the robot's memory |
| 6 | GitHub secrets and variables | where you hand all of the above to the robot |
| 7 | A Cloudflare account | hosts the customer pages behind the QR stands |

Keep this business separate from your other one: new Gmail, new Google Cloud project, new Sheet, new
password. Only your WhatsApp number is shared, so in WhatsApp Business give each business its own label.

---

## Step 1 – Why a public repository, and how to make one

### The 2,000 minutes, explained

> **Correction:** the "unlimited free minutes" below are real, but GitHub's terms only allow them for work on the
> software itself (building, testing, deploying), not for lead searching or sending e-mails. That is why this work
> now runs on your own computer ([LOCAL.md](LOCAL.md)). The public repository is still useful: Cloudflare builds
> the customer pages from it.

The robot (finding businesses, reading their websites, sending e-mails) does not run on your computer. It runs
on **GitHub Actions**: computers in GitHub's data centres that start on a timetable, do the job and switch off.
GitHub counts how long they run:

- **Private repository:** 2,000 free minutes a month, for all your private repositories together (about 33
  hours). When they are used up, the robot simply stops until the next month. Nothing is charged unless you add a
  payment method. One US city takes about 2–3 hours a day, so 2,000 minutes cover less than one city.
- **Public repository:** **unlimited free minutes**, and on bigger machines (4 processors instead of 2). Up to
  20 jobs can run at the same time, so all 30 US cities can be worked on every day. This is how we get "huge
  volume for free".

### Is public safe?

Public means anyone can **read the code**. It does not mean anyone can see your leads or passwords:

- Passwords go into GitHub **Secrets** (step 6). Secrets are never shown, not even to visitors of a public
  repository.
- Leads go into **your Google Sheet**, which only you can open.
- The robot's memory is saved **encrypted** with your `RQ_STATE_KEY`.
- The robot's logs only show counts ("312 businesses, 104 with e-mail"), never names or addresses.

Other ways to get more minutes:

- GitHub Pro costs about $4 a month for 3,000 minutes. That is still not enough for many cities.
- A "self-hosted runner" uses your own PC, which must then stay switched on.
- Opening several free GitHub accounts is against GitHub's rules. Don't.

### Why a **new** repository (not this one)

This private repository's history still contains a note about your other business from the day it was copied.
A new repository starts with a clean history, so nothing about the other business becomes public.

### Do it

1. Go to [github.com](https://github.com) and sign in.
2. Click the **+** at the top right → **New repository**.
3. **Repository name:** e.g. `review-leads` (any name; avoid your other business's name).
4. Choose **Public**.
5. Do **not** tick "Add a README", .gitignore or license. The repository must be empty.
6. Click **Create repository**.
7. Make sure Claude may push to it. Go to **Settings** (your profile picture → **Settings**) →
   **Applications** → **Claude** → **Configure**. If "Only select repositories" is chosen, add `review-leads` and
   **Save**.
8. Send me the name (`review-leads`). I push the code there with a clean history. From then on the new
   repository is the one you use, and the old private one can be archived.

---

## Step 2 – A new Gmail account (about 10 minutes)

1. Open [accounts.google.com/signup](https://accounts.google.com/signup) in a private/incognito window, so you
   are not signed in with your other accounts.
2. Fill in a name. Use your business name or your name plus the business, e.g. "Ravik | GuestEcho". Then
   birthday and gender.
3. Choose **Create your own Gmail address**, e.g. `guestecho.ravik@gmail.com`. Pick a professional-looking one,
   because businesses will see it.
4. Set a strong password and save it somewhere safe.
5. Add your phone number when asked, and type the code Google texts you.
6. Turn on **2-Step Verification** (required for the next step):
   [myaccount.google.com/security](https://myaccount.google.com/security) → **2-Step Verification** → **Get
   started** → follow the steps with your phone.
7. Create an **app password**. This is a special password only for the robot, so your real password never goes
   into GitHub:
   - Open [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) (sign in again if
     asked).
   - **App name:** `review robot` → **Create**.
   - Google shows a yellow box with 16 letters, like `abcd efgh ijkl mnop`. Copy it into a note now; Google shows
     it only once.
8. Make the account look real before it sends anything: add a profile photo or logo and send a few normal e-mails
   from it (to yourself, friends). New accounts that start with cold e-mails get blocked faster.

---

## Step 3 – Google Cloud service account (about 15 minutes)

This sounds technical but is only clicking. Stay signed in with the **new Gmail**.

1. Open [console.cloud.google.com](https://console.cloud.google.com). Accept the terms if asked. If a
   "Free trial" banner appears, **ignore it**: nothing here needs a credit card.
2. At the top left, click the project picker (it may say **Select a project**) → **New project**.
   - **Project name:** `review-leads` → **Create**. Wait a few seconds and make sure it is selected at the top.
3. Turn on the Sheets API: in the search bar at the top type **Google Sheets API** → open it → **Enable**.
4. Create the robot login:
   - Search bar: **Service accounts** → open it → **+ Create service account**.
   - **Service account name:** `sheet-writer` → **Create and continue** → skip the optional role steps →
     **Done**.
5. Copy its e-mail address from the list. It looks like
   `sheet-writer@review-leads-123456.iam.gserviceaccount.com`. You need it in step 4.
6. Download its key:
   - Click the service account → tab **Keys** → **Add key** → **Create new key** → **JSON** → **Create**.
   - A file like `review-leads-123456-abc123.json` downloads. **Treat it like a password**: never e-mail it,
     never upload it anywhere except GitHub Secrets (step 6).

---

## Step 4 – The Google Sheet (about 3 minutes)

1. Still signed in with the new Gmail, open [sheets.new](https://sheets.new). A blank sheet opens.
2. Click the title "Untitled spreadsheet" and name it `Review Leads`.
3. Click **Share** (top right):
   - Paste the service account e-mail from step 3.5.
   - Set it to **Editor**.
   - Untick **Notify people** → **Share**. If Google says the address is outside your organisation, click
     **Share anyway**.
4. Copy the **Sheet ID** from the address bar. In
   `https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789/edit#gid=0`
   the Sheet ID is the long part between `/d/` and `/edit`: `1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789`.

You don't need to create any tabs. The robot creates **Leads** and **Daily Report** itself, plus the outreach
tabs later.

---

## Step 5 – Your secret password `RQ_STATE_KEY` (2 minutes)

The robot remembers which businesses it has already checked, so it never does the same work twice. It saves this
memory encrypted with this password.

- Make a long random password of at least 30 characters. For example, use the password generator in your browser
  or phone, or type random letters, digits and symbols.
- Save it in your notes or password manager. If you lose it, the robot forgets its progress and starts again.
  The leads already in your Sheet stay.
- Use it only for this.

---

## Step 6 – Give everything to GitHub (about 10 minutes)

In the **new public repository**: **Settings** (tab at the top of the repository) → left menu **Secrets and
variables** → **Actions**.

### Secrets (tab "Secrets" → **New repository secret**, once per line)

| Name (type exactly) | Value |
|---|---|
| `RQ_SHEET_ID` | the Sheet ID from step 4.4 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | open the downloaded `.json` file with Notepad (Windows) or TextEdit (Mac), select all (Ctrl+A), copy, paste |
| `RQ_STATE_KEY` | your password from step 5 |
| `OUTREACH_GMAIL_ADDRESS` | the new Gmail address |
| `OUTREACH_GMAIL_APP_PASSWORD` | the 16 letters from step 2.7 (spaces don't matter) |
| `OUTREACH_SENDER_PHONE` | your WhatsApp number with country code, e.g. `+91 98765 43210` |
| `OUTREACH_POSTAL_ADDRESS` | your full postal address on one line, e.g. `12 Park Street, Kolkata 700016, India`. US law (CAN-SPAM) requires it in every e-mail; your home or office address is fine |
| `OUTREACH_NOTIFY_EMAIL` | optional: where "a business replied" alerts go (default: the new Gmail) |

### Variables (tab "Variables" → **New repository variable**)

| Name | Value | What it does |
|---|---|---|
| `FLEET_ENABLED` | `true` | the US cities are searched every day by themselves |
| `OUTREACH_ENABLED` | `true` | the outreach robot runs on US working days |
| `OUTREACH_LIVE` | **don't create it yet** | until it exists (with `true`), outreach only *prepares* e-mails for you to check |

Also tell me three things so I can put them in the settings: **your name**, **your business name** (as it should
appear in e-mails), and **your city**.

---

## Step 7 – Cloudflare account for the customer pages (about 10 minutes)

These are the pages behind the QR stands, and the free preview each business sees from your e-mail.

1. Open [dash.cloudflare.com/sign-up](https://dash.cloudflare.com/sign-up). Sign up with the new Gmail and a
   password, then confirm the e-mail Cloudflare sends.
2. In the left menu: **Workers & Pages** → **Create** → **Import a repository** (or **Connect to Git**).
3. Click **Connect GitHub**, allow Cloudflare to access the `review-leads` repository, then select it.
4. Settings:
   - **Project name:** `review-leads`. It must match the `name` in the repository's `wrangler.jsonc`; if you
     choose another name, tell me and I change the file.
   - **Build command:** `pip install -r site/requirements.txt && python site/build.py --preview`
   - **Deploy command:** `npx wrangler deploy` (Cloudflare fills this in)
   - **Root directory:** `/`
   - **Deploy**.
5. Every time the code on `main` changes, Cloudflare builds and publishes the pages again by itself.
   - If a build fails at **Cloning**, the repository is still empty: the code has to be pushed first.
   - If it fails at `pip`: **Settings** → **Build** → **Variables and secrets** → add `PYTHON_VERSION` = `3.12` →
     **Retry build**.
6. Your address is shown on the project's **Overview** page, like `https://review-leads.<your-name>.workers.dev`.
   Send it to me. I put it into the e-mails' preview links and the pages' legal notice, then switch the build from
   `--preview` to the final version.

---

## Step 8 – First run and daily routine

1. Repository → tab **Actions** → **US fleet (all cities in parallel)** → **Run workflow** → **Run workflow**.
   Leave the fields empty: all cities.
2. Each city appears as its own job. After about 30 minutes the first rows show up in the Sheet's **Leads**
   tab; the jobs finish after about 2.5 hours. Only businesses with an e-mail address or a WhatsApp number go
   into the Sheet. A **Daily Report** row per city shows the numbers.
3. From then on it runs by itself every day at about 06:20 UTC, night-time in the US.
4. Outreach, first as a test: **Actions** → **Outreach** → **Run workflow**. Check the **Email Preview** tab:
   these are the e-mails it *would* send. When you are happy, create the variable `OUTREACH_LIVE` = `true`. From
   the next working day it sends 15 e-mails a day, rising slowly to 40, so Gmail trusts the new account.
5. Every day: read the **Replies** tab. Answer the interested businesses quickly (docs/OUTREACH.md).

To pause everything: set `FLEET_ENABLED` and `OUTREACH_ENABLED` to `false`.

---

## Good to know

- **Sending is the real limit, not finding.** One new Gmail can safely send about 20–50 cold e-mails a day after
  warm-up. Google's hard limit is about 500 a day, and long before that cold e-mails land in spam or the account
  gets locked. The fleet finds tens of thousands of businesses, far more than one Gmail can write to in a year.
  More sending later means more Gmail accounts, each warmed up separately, or your own domain.
- **WhatsApp:** few US businesses publish a WhatsApp number. The ones that do are offered in the WhatsApp Queue
  tab, to send one by one by hand. Many strangers reporting your number gets it banned, and your other business
  uses the same number. Keep it to a handful a day, or use a second number.
- **GitHub pauses timetables** in public repositories after 60 days without any change to the code. If that
  happens, the Actions tab shows a button to re-enable them.
- **Cities:** the list is `config/us/fleet.toml` (30 cities). Tell me if you want more cities, or other
  countries: Canada, UK, Ireland, Australia, New Zealand, UAE and Singapore are prepared.
