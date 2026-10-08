# Setting up a customer

About 30 minutes per customer once you have done it twice.

## 1. Collect from the customer

| What | How they find it |
|---|---|
| **Google review link** | Signed in as owner or manager: search their business name on Google → *Ask for reviews* (or *Get more reviews*) → copy the link. It looks like `https://g.page/r/…/review`. Google can also make a QR code there. See [Google's help page](https://support.google.com/business/answer/16816815?hl=en) |
| No profile access? | Find the Place ID with Google's Place ID finder and use `https://search.google.com/local/writereview?placeid=<ID>`. Test this one on an iPhone: reports say it sometimes fails in Safari |
| **Payment link** (optional) | PayPal.me, a SumUp payment link, a Stripe Payment Link or a Square payment link. Restaurants that take cards at the table can skip it |
| **Menu link** (optional) | their PDF or menu page |
| **Brand colour** (optional) | e.g. `#8a2b2b` |

**Stripe and Square can send the guest back after paying.** Then the guest pays first and sees the review
button next. Point the redirect at our thank-you page:

- Stripe Payment Link: *After the payment → Don't show confirmation page → Redirect customers to your website →*
  `https://<site>/r/<id>/thanks.html`.
- Square payment link: *Redirect to a website after checkout*, same address.
- `python site/build.py` prints each customer's thank-you address.

## 2. Create the customer's file

Copy `site/businesses/demo-cafe.json` to `site/businesses/<id>.json`:

```json
{
  "id": "cafe-morgenrot",
  "name": "Café Morgenrot",
  "country": "DE",
  "timezone": "Europe/Berlin",
  "languages": ["de", "en"],
  "review_url": "https://g.page/r/XXXXXXXX/review",
  "menu_url": "https://cafe-morgenrot.de/karte.pdf",
  "payment": {"url": "https://paypal.me/cafemorgenrot", "label": "PayPal"},
  "brand_color": "#1f6f50",
  "pay_note": ""
}
```

- `id` is printed in the QR code (`/r/cafe-morgenrot/`). **Never change it after printing.** Every other field
  can change at any time.
- `payment: null` means no pay button. The page then says to pay at the table as usual (or shows `pay_note`).
- Only well-known payment and review addresses are accepted. For another provider, add `"allow_any_host": true`
  inside `payment`, after checking the link yourself.
- The first language in `languages` is the default page. The other is one tap away.

Commit and push. Cloudflare rebuilds in about a minute. Then open `https://<site>/r/<id>/` on a phone and test
both buttons.

## 3. QR codes and NFC stands

- **QR code:** `https://<site>/r/<id>/qr.svg` (made when `base_url` is set in `site/site.json`). It is a sharp
  vector, so it prints well at any size. Print it on table tents or stickers, or send it to the stand printer.
- **NFC:** buy NTAG213 stickers or cards. With the free *NFC Tools* app: *Write → Add a record → URL* →
  `https://<site>/r/<id>/`, then write. Optionally lock the tag so nobody can rewrite it.
- **Placement:** one stand per table plus one at the counter or till. The text on the stand should invite, not
  push. For example: "Bezahlen & Bewerten – scannen oder Handy auflegen" / "Pay & review – scan or tap".

## 4. What to tell the owner (Google's rules)

Give them this list. Breaking these rules can cost them their reviews (docs/COMPLIANCE.md).

- Never offer anything for a review: no discount, free coffee or prize draw.
- Ask everyone the same way. Never "If you liked it, review us", never only the happy ones.
- No tablet or phone at the till for guests to review on, and no pressure to review on the spot.
- No review targets for staff, and no "please mention my name".
- Answer reviews, the bad ones too, politely. Guests notice.

## 5. Guest messages by WhatsApp (package "Stands + guests")

1. **Consent first.** The restaurant adds the consent sentence (docs/COMPLIANCE.md, section 5) to its booking
   form, guest Wi-Fi page or a small sign-up card. Only guests who tick it are asked.
2. **Data processing agreement.** If you handle their guest list, sign one with the restaurant (*AV-Vertrag*,
   Art. 28 GDPR). Bitkom and many IHKs publish templates. If the restaurant runs the tool on
   its own laptop, the list never leaves it.
3. **Export the guests** as CSV with columns for name, phone, visit date and time, consent and (optionally)
   language. German or English column names both work: `Name;Telefon;Besuch;Einwilligung;Sprache`.
4. **Run it:**

   ```
   python -m guests.review_requests cafe-morgenrot guests.csv --stop stop.txt
   ```

   - It opens a page with one *WhatsApp* button per guest. Tap, check, send. This is free.
   - It only includes guests who agreed and visited 2 hours to 7 days ago.
   - Each guest gets one request in 90 days, then up to 3 short reminders: on days 2, 5 and 9 after it. Run the
     tool every day so reminders go out on time; they also reach guests who are no longer in the newest export.
     Fewer reminders: set `"reminders": 1` (or 0) in the business file.
   - `stop.txt` lists numbers that replied STOP, one per line. They are never asked again.
   - `--reviewed reviewed.txt` lists numbers of guests who have reviewed (the restaurant sees their names on
     Google). They get no more reminders.
5. **Automatic sending** (optional, paid per message: about €0.11 in Germany):
   - The restaurant needs a WhatsApp Business Platform number in Meta Business Suite. Such a number usually
     can't stay in the normal WhatsApp Business app as well. Meta's "coexistence" option allows both in some
     countries, so check before moving their main number.
   - Register a *Marketing* template named `review_request` with three variables. German example: "Hallo {{1}},
     danke für Ihren Besuch bei {{2}}! Wenn Sie mögen, erzählen Sie anderen auf Google davon: {{3}} Ob kurz oder
     lang, Ihre ehrliche Meinung hilft. Keine Nachrichten mehr? Antworten Sie STOP."
   - For the reminders, a second template named `review_reminder` with the same three variables, e.g. "Hi {{1}},
     just a friendly reminder in case you missed it: if you have a moment, you can share your experience at {{2}}
     on Google here: {{3}} No more messages? Reply STOP."
   - Then: `WHATSAPP_TOKEN=… WHATSAPP_PHONE_NUMBER_ID=… python -m guests.review_requests cafe-morgenrot
     guests.csv --send`.
   - It only sends between 10:00 and 20:00 local time.
   - Own wording goes into the customer file as `"whatsapp_text": {"de": "...{link}..."}`. The tool refuses
     texts that offer something, ask for five stars or only ask happy guests.

## 6. Keep the address alive

The stands point to your site, so **the site must stay online as long as the stands are in use**. A custom
domain of your own (about €10 a year) is safer than `workers.dev` in the long run: you can move hosting without
reprinting anything.

If a customer leaves, you have two choices:

- leave the page up (it costs nothing);
- set `payment` to `null` and keep only the review link.

Never point an old stand at something else.
