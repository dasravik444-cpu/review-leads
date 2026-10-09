# Running everything on your own computer (free)

The lead search, the e-mail hunt and the e-mails run on your own computer. GitHub only stores the code.

**Why not on GitHub any more?** GitHub's terms allow its free Actions computers only for building, testing and
deploying the software in a repository, not for other work such as searching the web for leads or sending
e-mails. After the 30-city run on 8 October, GitHub blocked Actions for the account ("owner invocation blocked").
Running it again there could get the whole GitHub account suspended. So the timers on GitHub are switched off.
Your own computer is free, and websites block a home internet connection much less than GitHub's computers.

## Android tablet or phone (about 30 minutes, once)

You type a few short commands into **Termux**, a free terminal app. Termux holds a small Ubuntu Linux in which the
robot runs exactly as on a computer.

**Step 1 – Install Termux.** In the tablet's browser open
[f-droid.org/packages/com.termux](https://f-droid.org/packages/com.termux/) → scroll to the newest version →
**Download APK** → open the downloaded file → if Android asks, allow installing apps from your browser →
**Install** → **Open**. (Termux recommends this F-Droid version.)

**Step 2 – One paste sets up everything.** In Termux, paste this line (long-press the black screen → **Paste**)
and press Enter:

```
curl -fsSL https://raw.githubusercontent.com/dasravik444-cpu/review-leads/main/android/setup.sh | bash
```

When Android asks whether Termux may access files, tap **Allow**. Wait 10-20 minutes until it says
**Done**. (If it stops with a question, press Enter. If it stops with an error, for example because the internet
dropped for a moment, paste the same line again: it carries on from where it stopped.) It downloads from Termux's
own server, installs only what the robot needs, and puts the robot in its own small Ubuntu named `review-leads`:
anything else you have in Termux stays as it is.

**Step 3 – Your Google key file.** It is the `.json` file you downloaded from Google Cloud during setup, in the
tablet's Download folder. (No longer there? Download a new one: [console.cloud.google.com](https://console.cloud.google.com)
→ project `review-leads` → search **Service accounts** → `sheet-writer` → **Keys** → **Add key** → **Create new
key** → **JSON** → **Create**.) Then type in Termux:

```
getkey
```

It takes only keys of the Google Cloud project `review-leads` (file names starting with `review-leads-`); keys of
your other business in the Download folder are left alone, and copies an older `getkey` took are removed.

**Step 4 – Your settings.** Type `settings`. A simple text editor opens. Move with the arrow keys in the key row
above the keyboard and type (or paste: long-press → Paste) after each `=`:
`RQ_SHEET_ID`, `OUTREACH_GMAIL_APP_PASSWORD`, `OUTREACH_SENDER_PHONE`, `OUTREACH_POSTAL_ADDRESS` (the table in the
Windows part below says what each one is). Save: tap **CTRL**, then the letter **o**, then Enter. Close: **CTRL**,
then **x**.

**Step 5 – Test.** Type `check`. The first time it installs what it needs (about 5 minutes). Look for
**`[OK] Google Sheet reachable`** and **`Gmail login OK`**.

If it says **`[FAIL] Google Sheet access ... HTTP 403`**, the Sheet does not let that Google key in. The line
`[OK] Google service-account key set - …@….iam.gserviceaccount.com` shows the key's address: open the Sheet →
**Share** → paste the address → **Editor** → untick **Notify people** → **Share**, then `check` again. (Still 403?
Then `RQ_SHEET_ID` is probably another Sheet's: fix it with `settings`.)

**Step 6 – Switch the robot on.** Type `robot on`. From then on it works by itself, every day:

| When (India time) | What |
|---|---|
| 11:00 | gets the newest version (keeps it only if it starts cleanly) |
| 13:00 | the next US city: an hour of search, then 30 minutes of e-mail hunt (Austin gave 2,171 businesses) |
| 17:30 | an hour more of e-mail hunt for businesses of earlier cities that still have no e-mail |
| 20:05 - 02:05 (from 1 November 21:05 - 03:05), US Monday-Friday | e-mails, every hour at 09:35-15:35 Chicago time: first e-mails with the PDF, follow-ups, replies and bounces |
| 00:30 | a backup of its memory into the tablet's Documents folder (`review-leads-backup`, last 7 days) |

Every business with an e-mail, WhatsApp or phone number goes into the Sheet. E-mails start at 15 a day and rise by
5 every 3 sending days to 40 (a new Gmail that sends much more is soon treated as spam). `robot status` shows what it does,
the last and next run of each job, and per city how many businesses it found and how many have an e-mail and a
phone. `robot log` shows today's log, `robot off` stops it (the job it is on saves first), `robot run leads` runs
a job now. It starts again by itself after a restart of the tablet (Termux:Boot app) and within 15 minutes if
Android closes it (Termux:API app); both apps are already there for Plant Parlour. Keep the tablet charging and on
Wi-Fi, and Termux on **Battery: Unrestricted** and **Autostart: on** (Settings → Apps → Termux). More than one city a
day: `ROBOT_CITIES_PER_DAY=2` in `settings`; a job off: `ROBOT_EMAILS=no` (or `ROBOT_LEADS=no`).

**By hand instead:** `leads` finds businesses (3 cities, about 4½ hours; `leads --count 1` one city), `emails` sends
this hour's share of the day's e-mails between about **8 PM and 3 AM India time** on US working days. A command typed
while the robot is busy says so and waits for you to try again. `update` gets the newest version of everything.

**Your PDF and lead lists from GitHub: `import`.** Every first e-mail carries the 2-page GuestEcho PDF. Save your
own copy (the one with your WhatsApp number) into the tablet's Download folder, then type `import`: from then on
that one is attached. `import` also adds lead lists you downloaded from GitHub (`leads-<city>.zip`) to the Sheet:
today's rules are applied again (big chains and addresses that are not the business's are left out), businesses
already in the Sheet stay exactly as they are, and none gets a Lead ID another business already has. A GitHub list
is downloaded while signed in to GitHub, from the run's page → **Artifacts** (it stays there 7 days after the run).

**A test e-mail first.** `emails --max 1 --copy-to your@gmail.com` sends one real e-mail to the next lead and a
blind copy to you, so you see exactly what the business gets (the PDF too). About 15 minutes later,
`emails --check` reads the replies and bounces (any time of day, nothing is sent): a bounce shows up there and in
the Sheet.

**Next to Plant Parlour in the same Termux.** The two run side by side without touching each other:

| | Review business (this robot) | Plant Parlour |
|---|---|---|
| Commands | `getkey` `settings` `check` `leads` `emails` `update` | `pp …` (`pp status`, `pp check` …) |
| Ubuntu inside Termux | `review-leads` | `pp-ubuntu` |
| Google Cloud key, Sheet, Gmail | project `review-leads`, its Sheet, das.ravik002@gmail.com | its own |
| Runs | by itself once switched on (`robot on`), at its own times | by itself, on its timetable |

This robot never changes Termux's shared parts once they work (proot-distro, the package lists), never releases the
keep-awake lock Plant Parlour holds, and keeps its memory use for the map data under 2 GB. Its robot uses its own
start-up file (`~/.termux/boot/review-leads`), folder (`~/.review-leads`) and 15-minute check (job 7711; Plant
Parlour's is 4711), and its lead search starts at 13:00, after Plant Parlour's 06:00 lead run.

## One-time setup (Windows, about 20 minutes)

**Step 1 – Install Python.**
Open [python.org/downloads](https://www.python.org/downloads/) → click the yellow **Download Python 3.x** button
→ open the downloaded file. On the first screen tick **"Add python.exe to PATH"** (bottom) → **Install Now** →
when it says "Setup was successful" → **Close**.

**Step 2 – Download the code.**
Open [github.com/dasravik444-cpu/review-leads](https://github.com/dasravik444-cpu/review-leads) → green
**<> Code** button → **Download ZIP**. In your Downloads folder: right-click `review-leads-main.zip` →
**Properties** → if there is an **Unblock** box at the bottom, tick it → **OK**. Then right-click the ZIP →
**Extract All…** → **Extract**. Open the new folder (and the folder of the same name inside it, if there is one)
until you see `run_check`, `run_leads`, `run_emails`, `settings-example` and a `secrets` folder. This is
"your folder" from now on; you can move it to Documents.

**Step 3 – Your Google key file.**
Find the `.json` key file you downloaded from Google Cloud during setup (in Downloads, named like
`review-leads-123456-a1b2c3d4e5.json`) and drag it into the `secrets` folder. Any name is fine.
Can't find it? [console.cloud.google.com](https://console.cloud.google.com) → project `review-leads` →
search **Service accounts** → click `sheet-writer` → tab **Keys** → **Add key** → **Create new key** → **JSON** →
**Create**. Drag the new file into `secrets`. (The Sheet is shared with this account already.)

**Step 4 – Your settings.**
Double-click **`run_check`**. The first time it creates `settings.txt` and opens it in Notepad. Type after each `=`:

| Line | What to type |
|---|---|
| `RQ_SHEET_ID=` | your Sheet's ID: in the Sheet's address `…/spreadsheets/d/`**`1AbC…xyz`**`/edit`, the long bold part |
| `OUTREACH_GMAIL_ADDRESS=` | already filled in: `das.ravik002@gmail.com` |
| `OUTREACH_GMAIL_APP_PASSWORD=` | the 16-letter app password (spaces don't matter). Lost it? Make a new one at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) while signed in as das.ravik002 |
| `OUTREACH_SENDER_PHONE=` | your WhatsApp number, e.g. `+91 98765 43210` |
| `OUTREACH_POSTAL_ADDRESS=` | e.g. `12 Park Street, Kolkata 700016, India` |

Save with **Ctrl+S**, close Notepad.

**Step 5 – Test.**
Double-click **`run_check`** again. The first time it installs what it needs (a few minutes of text scrolling by).
Then look for **`[OK] Google Sheet reachable`** and **`Gmail login OK`**. Press a key to close the window.
(If Windows shows "Windows protected your PC": **More info** → **Run anyway**. The file is yours.)

## Every day

- **Find leads:** double-click **`run_leads`**. It takes the next 3 US cities (cities not yet in your Sheet first:
  Washington DC, Boston, Nashville, Las Vegas, Miami…), searches each for about an hour, then hunts e-mail
  addresses for 30 minutes each, and adds the businesses with an e-mail to your Sheet. That is about 4½ hours:
  keep the computer plugged in and awake (**Settings → System → Power → Screen and sleep → When plugged in, put my
  device to sleep after: Never**). You can close the window any time: what was found so far is kept, and the
  next run continues. Your Sheet already holds many thousands of businesses, so once or twice a week is plenty.
- **Send e-mails:** double-click **`run_emails`** on US working days (Monday to Friday there), between about
  **8 PM and 3 AM India time**. Outside that it refuses, so your e-mails don't arrive at night. It sends today's
  e-mails a few minutes apart (15 a day at first, rising slowly to 40), sends the follow-ups that are due, and
  reads the replies into your Sheet. Leave the window open until it says it is done (30–90 minutes).
- **Test without sending:** in your folder, click the address bar, type `cmd`, press Enter, and type
  `python scripts\local_run.py emails --dry-run`. The e-mails it would send appear in the Sheet's
  "Email Preview" tab. `python scripts\local_run.py import` adds lead lists from your Downloads folder (see the
  Android part above).

## Let Windows do it by itself (optional)

**Start** → type **Task Scheduler** → open it → **Create Basic Task…** → Name `Send e-mails` → **Weekly** →
start time **8:45 PM**, tick Monday to Friday → **Start a program** → **Browse** → pick `run_emails.bat` in your
folder → in **Start in** type your folder's path (copy it from Explorer's address bar) → **Finish**. Then open the
task's **Properties → Settings** and tick "Run task as soon as possible after a scheduled start is missed".
Make a second task the same way for `run_leads.bat` at a time the computer is on anyway.

## Good to know

- Each city's memory is a file in the `data` folder. Don't delete it: it remembers which businesses were already
  checked. Back up the `data` folder and `settings.txt` now and then.
- To update the code later: download the ZIP again and copy `settings.txt`, the `secrets` folder and the `data`
  folder from the old folder into the new one.
- Settings live in `config/us/_base.toml` (for example `email_search = false` stops the web search).
- On a Mac: install Python from python.org, download and unzip the same way, then open Terminal, type `cd ` (with a
  space), drag your folder into the Terminal window, press Enter, and use `bash run_check.sh`,
  `bash run_leads.sh`, `bash run_emails.sh`.
- An always-on free alternative to your own computer is Oracle Cloud's "Always Free" virtual machine (it asks for
  a card to check who you are). The same commands work there.
