# Working on this repository (read first)

The owner runs this robot (Aurenflow review-QR outreach, India) on an Android device in Termux and talks to you
from their phone. They are not a programmer: give exact commands to type, one per line, and say what each does.

## One robot, two devices: the tablet and the phone

- The robot normally runs on the owner's **Android tablet** (Termux + proot Ubuntu `review-leads`, next to Plant
  Parlour). From **16 October 2026 for about 3-4 days** it runs on the owner's **phone** instead (the owner travels).
- **Only one device may run it at a time** (two would e-mail the same businesses and go over Gmail's limit). The
  memory moves with it: `robot off` + `move out` on one device (scripts/move.py writes
  `review-leads-move.zip` into Download and keeps that device's robot off), Quick Share, then `move in` +
  `check` + `robot on` on the other.
- **Never make a change that makes it harder to switch back to the tablet.** Every change must work the same on the
  tablet and the phone: same scripts (android/*.sh, scripts/*), same commands, same data layout (data/*.sqlite,
  settings.txt, secrets/), no step that only one of them has. When the owner says they are back on the tablet, the
  way back is: phone `robot off`, `move out`, Quick Share; tablet `update`, `move in`, `check`, `robot on`. Check
  that this still works (tests/test_move.py) before every push.
- Do not ask the owner to change anything on the tablet while the phone runs the robot.

## How the owner wants to work

- Don't make things up, don't guess: check the code, test it, and ask when something is really theirs to decide.
- Test before pushing (`python -m pytest -q`; `ruff check --select F,E9 .`); push straight to `main`; no pull
  request unless asked; no model names in commits.
- Never ask for the Gmail app passwords, the Google key file or other secrets in chat: the owner types them into
  `settings` / copies the key with `getkey`.
- Never put the owner's phone number or address in this (public) repository: only their own PDF copy carries it
  (built locally, gitignored, sent to them as a file).
- Lead search and outreach never run on GitHub Actions; never route around a blocked network request.
- Give short live updates while working; tell plainly what works, what was tested and what is still a risk.

## The business, as of 16 October 2026

- Market India (MARKET=in): premium cafés, restaurants, bars, salons and gyms; Bengaluru first, then Kolkata,
  Chennai, Delhi, Mumbai (config/in/fleet.toml).
- Two Gmail accounts, each up to 400 e-mails a day (800 in all, follow-ups included), by the sending plan in
  config/in/_base.toml; the bounce brakes stop a bad batch (12% of 60+), not a normal day (~9% bounces).
- No prices anywhere a business sees them (PDF, e-mails, WhatsApp) since 15 October 2026.
- WhatsApp is sent by hand from the device (`whatsapp`, 7 AM - 9 PM); missed days pile up (up to 7 days' worth).
