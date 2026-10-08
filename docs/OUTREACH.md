# Outreach: e-mails and WhatsApp (letters where e-mail needs consent)

The workflow **Outreach** reads the Leads tab, follows the country's rules (docs/COMPLIANCE.md) and fills these
tabs of the Sheet. For the US it uses `config/us/outreach.toml`: one Gmail for the leads of all US cities.

| Tab | What it is |
|---|---|
| **Letters** | Today's letters: name, street, postcode, city, the full personalised text and the preview link |
| **Email Preview** | In dry-run: exactly what would be e-mailed |
| **Outreach** | Every e-mail conversation and its state |
| **Replies** | Replies, sorted: interested / not interested / other |
| **WhatsApp Queue** | One-tap links: tap, check the text, press send in WhatsApp Business |
| **Do Not Contact** | Everyone who said no, bounced or asked to be removed. Add rows yourself any time |
| **Outreach Report** | One line per day |

Nothing is sent until the variable `OUTREACH_LIVE` is `true`. It runs every hour on US working days, 09:41 to
16:41 Central time. Runs outside the sending window do nothing.

## What happens to a lead, by country

The **Contact Rule** column of the Leads tab says it for every lead.

| Country | First contact | E-mail | WhatsApp |
|---|---|---|---|
| Germany | Letter (15 a day) | Only after they asked: they replied, called, or you set Status to **Opted in** | Only to those who said yes |
| UK | E-mail to Ltd/LLP/PLC. Letter to sole traders and partnerships | Limited companies | Only to those who said yes |
| USA | E-mail | Yes, with your postal address and an opt-out | One by one, only to numbers the business publishes as WhatsApp (leads without e-mail) |
| Canada, New Zealand | E-mail to an address the business publishes | Published addresses only, about its business | Only to those who said yes |
| Ireland | Like the UK | Companies (Ltd/DAC/PLC) | Only to those who said yes |
| UAE | E-mail | Yes | One by one to published WhatsApp numbers |
| Singapore | E-mail with `<ADV>` before the subject | Yes | Only to those who said yes |
| Australia | E-mail to an address the business publishes | Published addresses only, never guessed ones | Only to those who said yes |

E-mails are a short first message plus follow-ups (US: after 3 and 7 days). Rules that apply everywhere:

- Every reply stops the sequence.
- "No", "nein", "abmelden" or "unsubscribe" adds the business to Do Not Contact.
- A bounce stops that address. Too many bounces pause sending by itself.
- Sending starts at 15 a day (US) and rises by 5 every 3 days up to 40, so Gmail trusts the new account.
- E-mails go out only in office hours, in the campaign's time zone.

## The Status column

The system writes these statuses:

- *Letter queued*, *Letter sent*;
- *Emailed*, *Emailed (follow-up 1)*, *Emailed - no reply*;
- *Replied - read it*, *Interested - call now*;
- *Not interested (opted out)*, *Email bounced*.

**Anything else you type** (*Customer*, *Called*, *Do not contact*...) means hands off: the system never touches
that lead again. Type **Opted in** when a business asked to hear from you. In Germany that is the only way it
gets an e-mail.

## Your daily routine (15 minutes)

1. **Letters tab** (only Germany, UK and Irish sole traders; empty for the US):
   - Send the day's letters through an online letter service. Upload a PDF made from the text, or send each row.
   - Write the result in the **Result** column: `Sent`, `Returned (bad address)`, `Interested`, `Not interested`
     or `Skip`.
   - *Interested* moves the lead to *Interested - call now*. A business that wrote or called you has contacted
     you, so you may answer by phone, e-mail or WhatsApp.
2. **Replies tab**: answer the interested ones the same day. The notification e-mail tells you when one arrives.
3. **WhatsApp Queue**: businesses that said yes, plus (US, UAE) businesses without an e-mail that publish a
   WhatsApp number, at most a handful a day. Tap, check, send. Then write the result: `Sent`, `Not on WhatsApp`,
   `Replied`, `Interested`, `Not interested` or `Skip`. Your number is shared with your other business. If many
   strangers report it, WhatsApp bans it for both, so never add more.
4. **A new customer**: set Status to *Customer* and follow docs/CUSTOMERS.md.

## The texts

The German and English texts live in `leadgen/outreach/templates.py`: subjects, first e-mail, follow-ups, the
letter and the WhatsApp message. They are short, say who you are and where you found the business, and offer the
free preview. You can replace a text in the campaign config:

- `[outreach.letters] text`;
- `[outreach.email] first`, `subjects`, `follow_ups`;
- `[outreach.whatsapp] message`.

`python -m leadgen doctor` checks that every placeholder exists.

Placeholders you can use include `{business}`, `{greeting}`, `{person}`, `{place}`, `{offer}`, `{demo_link}`,
`{sender_name}`, `{sender_business}`, `{sender_phone}` and `{sender_address}`.

The preview link is your `demo_url` plus the business name, e.g. `…/demo/?n=Café%20Morgenrot&lang=de`. It shows
the business its own page before it buys.

## Testing

- *Actions → Outreach → Run workflow* with `mode = dry-run`: fills the previews and sends nothing.
- `max_emails = 1` with `mode = live`: sends exactly one e-mail. Send it to yourself first: add your own address
  as a test lead with Status *Opted in*.
