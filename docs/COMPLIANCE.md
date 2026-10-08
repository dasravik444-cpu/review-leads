# Rules: reviews, outreach and privacy (Germany, UK, US, Australia)

This is a working summary of the research behind the system, with sources, written 8 October 2026. It is
**not legal advice**. The rules differ by country and change (Google changed its review rules twice in 2026).
Before you send the first letters in Germany, pay a German competition lawyer (*Fachanwalt für
Wettbewerbsrecht*) for a one-off check of the letter text and of the guest-consent wording below. Do the same for
each new country.

## 1. One-page summary

| | Germany | UK | USA | Australia |
|---|---|---|---|---|
| **First contact with a business (our sales)** | Letter. No cold e-mail, WhatsApp or cold calls | E-mail to limited companies (Ltd/LLP/PLC). Letter to sole traders and partnerships | E-mail (opt-out law) | E-mail only to an address the business publishes itself, about something relevant to it |
| **What every e-mail needs** | Their prior consent | Who we are, a working opt-out | Truthful sender and subject, our postal address, a working opt-out | Who we are, a working unsubscribe |
| **Review request to a guest (WhatsApp/SMS)** | Only with the guest's consent | Only with consent | Only with consent | Only with consent |
| **Reviews (all countries)** | Ask everyone the same way. Nothing in return. No pre-filtering. No pressure on the premises. No staff quotas or "mention my name" | same | same | same |

`leadgen/country.py` turns each column into rules the outreach engine follows (the **Contact Rule** column of
the Leads tab shows the rule for every lead). `guests/review_requests.py` and `site/build.py` follow sections 2
and 5.

## 2. Google's review rules (they bind our customers, so they bind the product)

Google's Maps content policy lists what a business may **not** do with reviews:

- **Selective asking.** It must not "discourage or prohibit negative reviews, or selectively solicit positive
  reviews from customers". This rules out *review gating*, where a "Were you happy?" screen sends happy guests to
  Google and unhappy ones to a private form.
- **Incentives.** No money, discounts, free items or prize draws for a review, and none for changing or
  removing one.
- **Pressure on the premises.** It must not "require or pressure users to leave ratings or write reviews while on
  the premises".
- **Staff, added in April 2026.** No "requesting that staff solicit a certain number of reviews". Also no
  "requesting that staff solicit reviews that include specific content, including content that identifies a staff
  member". Reviews that name staff have been removed since.

Sources: [Google Maps content policy](https://support.google.com/contributionpolicy/answer/7400114),
[ppc.land on the April 2026 change](https://ppc.land/google-tightens-maps-review-policy-staff-names-and-quotas-now-banned/),
[Search Engine Roundtable](https://www.seroundtable.com/google-reviews-policy-staff-mentions-solicitations-41175.html),
[Google: how Maps fights fake content](https://blog.google/products/maps/how-google-maps-protects-against-fake-content/),
[Google: create a review link or QR code](https://support.google.com/business/answer/16816815?hl=en).

**Enforcement.**

- Breaking these rules can remove reviews and put a warning on the profile.
- Google can also pause new reviews when it sees unusual activity. Review-software vendors report businesses
  losing their whole review history.
- Google says it blocked or removed more than 292 million policy-violating reviews in 2025.
- Reviews posted in bursts, or many from one device or network, are reported to get filtered
  ([Whitespark](https://whitespark.ca/blog/google-remove-reviews/)).
- So the product never uses a tablet or kiosk at the till: every guest reviews on their own phone.

**How the product follows this:**

- The QR/NFC page offers *Pay* and *Review* side by side. The review is marked optional, and the page never asks
  "were you happy?" (`site/build.py`).
- The page is passive: a stand on the table, not staff asking at the till. Whether even a passive QR stand
  counts as "on the premises" is not settled. Commentators disagree, and Google gives no example. The
  safest form is the one we use: optional, nothing in return, never pushed.
- Guest messages go to everyone who agreed, in the same words, after the visit. Texts that offer something, ask
  for five stars or only ask happy guests are refused (`guests/review_requests.py`).
- Tell every customer: no staff quotas, no "please mention Anna", no bonus tied to review counts.

## 3. Consumer law on reviews

The national laws below sit on top of Google's rules. They are stricter about hiding negative reviews. They are
looser than Google about incentives, but Google's own ban applies anyway.

- **USA, FTC rule on consumer reviews (16 CFR Part 465), in force since 21 October 2024.** It bans fake reviews,
  rewards that depend on what the review says, and *review suppression*. Penalties are up to $53,088 per
  violation. Sources: [FTC final rule](https://www.ftc.gov/system/files/ftc_gov/pdf/r311003consumerreviewstestimonialsfinalrulefrn.pdf),
  [16 CFR 465](https://federal-regs.com/title/16/part-465/),
  [FTC: soliciting and paying for reviews](https://www.ftc.gov/business-guidance/resources/soliciting-paying-online-reviews-guide-marketers).
- **UK, DMCC Act 2024, Schedule 20 para 13, since 6 April 2025.** Fake reviews and hiding genuine ones are
  banned outright. The CMA's guidance (CMA208) says not to limit "invitations to review ... in order to avoid
  negative reviews". Fines go up to 10% of global turnover. In March 2026 the CMA opened five investigations,
  including Just Eat and Pasta Evangelists. Sources: [CMA208](https://gov.uk/government/publications/fake-reviews-cma208),
  [Slaughter and May](https://thelens.slaughterandmay.com/post/102l6s8/cma-clarifies-expectations-on-consumer-reviews-but-uncertainties-remain),
  [RPC on the investigations](https://www.rpclegal.com/snapshots/consumer/summer-2026/cma-launches-5-x-investigations-into-fake-and-misleading-review-practices/).
- **Australia, Australian Consumer Law (s 18, s 34) and ACCC guidance.** Asking only the customers you expect
  to be happy can mislead. In *ACCC v Meriton* (2017) the hotel group did this by hiding unhappy guests' e-mail
  addresses from TripAdvisor's review invitations. Any reward must be open to everyone, whatever they write.
  Sources: [ACCC guidance](https://www.accc.gov.au/media-release/accc-releases-guidance-about-online-product-reviews),
  [ACCC: online reviews](https://www.accc.gov.au/business/advertising-and-promotions/online-reviews-for-product-and-services).
- **EU / Germany.** Since 2022 the EU's consumer-law update (in Germany the UWG annex, Nr. 23b/23c) bans fake
  and commissioned reviews. This item is background knowledge and was not part of the research above.

## 4. Contacting businesses (our own sales)

### Germany: letters, not e-mails

- **E-mail and messenger advertising need the recipient's prior express consent, businesses included**
  (§ 7 Abs. 2 Nr. 2 UWG). WhatsApp counts as electronic mail. An offer e-mail or a follow-up is already
  advertising. GDPR "legitimate interest" does not replace this consent. Competitors and associations send
  formal warning letters (*Abmahnungen*) with legal costs.
- **Phone calls to businesses** need at least *presumed* consent (§ 7 Abs. 2 Nr. 1 UWG). Courts read this
  narrowly. Someone selling their own service cannot rely on a directory listing (BGH I ZR 191/03). So: **no cold
  calls either.**
- **Letters are allowed**, unless the business has said it does not want advertising. The engine skips websites
  whose Impressum says *Werbung untersagt* or similar (the "Objects to advertising" signal).
- **A review request is advertising too.** The BGH said so for a feedback request sent inside an invoice e-mail
  (VI ZR 225/17, 10 July 2018). This matters for guest messages (section 5).
- What the system does: in Germany the first contact is a **letter** (Letters tab, 15 a day). E-mail goes only to
  businesses that asked for it: they replied, called, or you set their Status to **Opted in**. WhatsApp goes only
  to businesses that said yes.

Sources: [UWG § 7](https://www.gesetze-im-internet.de/uwg_2004/__7.html),
[IHK Ostwestfalen: Werbung per Telefon, Brief und E-Mail](https://www.ostwestfalen.ihk.de/fileadmin/Dokumente/Recht/Merkblaetter-Recht/Werbung_per_Telefon__Brief_und_E-Mail.pdf),
[IHK Pfalz: Telefonwerbung](https://www.ihk.de/pfalz/recht/wettbewerb/werbung2/telefonwerbung-1274014),
[Händlerbund on BGH VI ZR 225/17](https://ohn.haendlerbund.de/recht/urteile-entscheidungen/32433-bgh-bitte-positive-bewertung-unzulaessige-werbung).

**GDPR applies on top**, because a sole trader's name and address are personal data:

- Our letter says where we found the details: their website, OpenStreetMap and Overture Maps.
- It says why we write, and that a short message stops all further contact (Art. 14 and Art. 21 GDPR).
- The privacy page in `site/` repeats this.
- Anyone who objects goes on the Do Not Contact tab.

### UK: limited companies by e-mail, everyone else by letter

- PECR regulation 22 requires consent (or the "soft opt-in") for marketing e-mails to *individual* subscribers.
  These include sole traders and some partnerships.
- *Corporate* subscribers can be e-mailed without consent: limited companies, LLPs, PLCs and Scottish
  partnerships. Every message must still say who we are and offer a working opt-out.
- From 5 February 2026 PECR fines go up to £17.5m or 4% of turnover.
- The engine reads the legal form from the business's website (the **Legal Form** column). It e-mails only Ltd,
  LLP and PLC, and queues a letter for the rest.

Sources: [ICO: business-to-business marketing](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/business-to-business-marketing/),
[ICO: e-mail marketing rules](https://ico.org.uk/for-organisations/guide-to-pecr/guidance-on-direct-marketing-using-electronic-mail/what-are-the-rules-on-direct-marketing-using-electronic-mail).

### USA: e-mail allowed, with CAN-SPAM's conditions

- No prior consent is needed. B2B e-mail is covered by CAN-SPAM like any other e-mail.
- Every e-mail needs truthful headers and subject, a clear statement that it is an advertisement, and **our valid
  postal address**.
- It also needs an opt-out that works for at least 30 days. Opt-outs must be honoured within 10 business days.
- Penalties are up to $53,088 per e-mail. Some states (California) add rules.
- The engine refuses to send without `OUTREACH_POSTAL_ADDRESS`. Its footer has the address and the opt-out.

Source: [FTC CAN-SPAM compliance guide](https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business).

### Australia: only published addresses, and check one point first

- The Spam Act 2003 allows *inferred* consent only when all of these hold:
  - the business **conspicuously publishes** the address;
  - there is no "no commercial messages" statement next to it;
  - the message relates to the recipient's role or business.
- Every message must say who we are and have an unsubscribe.
- The engine e-mails only addresses found on the business's own pages, never guessed ones (`published_role`).
- **Open question before any Australian campaign.** The Act also bans using "address-harvesting software" and
  lists made with it. Spam operator Clarity1 was fined in federal court partly for this. Our website crawler
  collects published addresses. Get Australian advice on whether that counts before sending a single e-mail
  there.

Sources: [Spam Act 2003](https://legislation.gov.au/Details/C2016C00614),
[Mondaq: spamming and the Spam Act](https://www.mondaq.com/australia/consumer-law/996226/spamming-and-the-spam-act),
[conspicuous publication rule](https://emaillistvalidation.com/blog/conspicuously-published-address-rule-australian-spam-act/),
[Pointon Partners](https://pointonpartners.com.au/spam-act/).

### Other English-speaking markets (packs ready, rules from background knowledge)

These packs exist in `leadgen/country.py`. Their rules come from background knowledge, not from the research
above. Check before a large campaign there.

- **Canada (CASL):** implied consent for an address the business conspicuously publishes, when the message is
  about its business and no "no unsolicited messages" notice is published. Every message needs your name,
  mailing address and an unsubscribe, honoured within 10 business days. Pack rule: `published_role`, postal
  address required.
- **Ireland:** company addresses (Ltd, DAC, PLC) may be e-mailed about their business with an opt-out. Sole
  traders need consent. This is the same approach as the UK (the earlier research found Ireland allows corporate
  addresses with conditions).
- **New Zealand (Unsolicited Electronic Messages Act 2007):** inferred consent from a conspicuously published
  business address, as in Australia.
- **UAE:** no specific cold e-mail rule for businesses was found. The PDPL protects personal data. WhatsApp is the
  normal business channel there, so the queue offers published WhatsApp numbers one by one.
- **Singapore (Spam Control Act):** unsolicited commercial e-mail sent in bulk must start its subject with
  `<ADV>`, include contact details and an unsubscribe. The pack adds `<ADV>` automatically.

### Other European countries (not built yet)

- **The Netherlands** is unclear since its 2021 changes.
- **France's** CNIL accepts B2B e-mail that relates to the person's job, with a simple opt-out.
- **Austria** and **Switzerland** are believed to require consent for e-mail advertising to businesses too. This
  comes from background knowledge and has not been researched.

### How strict is strict enough?

The country rules stay switched on. In the US they cost almost nothing: cold e-mail is allowed, and the system
simply adds what CAN-SPAM asks for (your address, an opt-out, an honest subject). They also protect you, not
only the law:

- Gmail locks accounts that get spam complaints.
- WhatsApp bans numbers that strangers report, and your number is shared with your other business.
- In Canada, the UK and Australia, fines are real and enforced.

A rule can be changed per country in its pack if you decide otherwise.

## 5. Review requests to a restaurant's guests (WhatsApp / SMS)

- **Consent first, everywhere.** In Germany a review request is advertising (BGH VI ZR 225/17), so an e-mail or
  WhatsApp needs the guest's prior express consent.
  - The narrow existing-customer exception (§ 7 Abs. 3 UWG) is disputed for review requests. Don't rely on it.
  - In the US, texts fall under the TCPA ($500–$1,500 per text). WhatsApp's own Business Messaging Policy also
    requires opt-in before a business messages someone.
  - `guests/review_requests.py` only asks guests marked as consenting.
- **Consent wording** for the restaurant's booking form, guest Wi-Fi page or a sign-up card. Ask the lawyer to
  check it:
  - DE: *„Ja, schicken Sie mir nach meinem Besuch eine WhatsApp-Nachricht mit der Bitte um eine
    Google-Bewertung. Ich kann jederzeit mit STOP widersprechen."*
  - EN: *"Yes, send me one WhatsApp message after my visit asking for a Google review. I can reply STOP at any
    time."*
- **Same message for everyone who agreed.** No "were you happy?" step first and nothing offered in return (sections
  2 and 3). The tool asks each guest once per 90 days, from 2 hours to 7 days after the visit, then sends at most
  3 short reminders (days 2, 5 and 9; the business setting `reminders` lowers this, 0 = none), and never after STOP.
- **Who is responsible.**
  - The restaurant is the data controller of its guest list. If we run the tool for it, we are its processor and
    need a data processing agreement (*Auftragsverarbeitungsvertrag*, Art. 28 GDPR) with it.
  - The one-tap mode can run entirely on the restaurant's own laptop. The guest list then never leaves the
    restaurant.
  - Guest lists, pages and state files are excluded from git (`.gitignore`).
- **WhatsApp Business Platform (paid API).** Review requests are best registered as a *Marketing* template.
  Meta reclassifies "utility" templates that ask for something.
  - Germany's rates in 2026 are about €0.1131 per marketing message and €0.0456 per utility message, plus VAT.
  - From 1 October 2026, replies inside the 24-hour window are reported to be billable too.
  - Sources: [ChatMaxima: Germany rates](https://chatmaxima.com/whatsapp-api-pricing/germany/),
    [Wati: template categories](https://support.wati.io/en/articles/11463465-whatsapp-template-categories-explained-utility-authentication-and-marketing).

## 6. Our own web pages (`site/`)

- **Impressum** (§ 5 DDG, which replaced the TMG in May 2024): name, a real postal address and e-mail. A foreign
  address is fine; a P.O. box is not. `site.json` holds it, and the build refuses to publish while it still says
  FILL_IN.
- **No cookies, no tracking, no fonts or scripts from other sites**, so no cookie banner is needed (§ 25 TDDDG).
  The privacy page still explains the hosting provider's server logs (Art. 13 GDPR). If you ever add analytics,
  this changes.
- **Payment links** come only from the customer's file and only from known providers. Nobody can swap in another
  payee by editing a link.

Sources: [IHK München: Impressum](https://www.ihk-muenchen.de/ratgeber/recht/internetrecht/impressum/),
[IHK Köln: Regeln für Cookies](https://www.ihk.de/koeln/hauptnavigation/recht-steuern/regeln-fuer-cookies-ttdsg-5259484),
[Datenschutz-Generator: TDDDG und Cookies](https://datenschutz-generator.de/tdddg-cookies/).

## 7. What the code enforces

| Rule | Where |
|---|---|
| Country rules per lead (Contact Rule column) | `leadgen/country.py`, `leadgen/report.py` |
| Germany: letters first, e-mail only to "Opted in" | `leadgen/outreach/engine.py` (`_pick`, `_letters_queue`) |
| UK: e-mail only Ltd/LLP/PLC | `engine._pick` with the Legal Form column |
| US: postal address in every e-mail | `engine._sender_problem`, `templates.py` footer |
| Australia: only addresses the business published | `engine._pick` (`published_role`) |
| Skip businesses that object to advertising | `enrich/extract.py` (`no_marketing_notice`), `engine` |
| Opt-outs and bounces stop all contact | Do Not Contact tab, `engine._suppress_lead` |
| QR page: optional review, no gating, no cookies | `site/build.py`, `site/assets/r.js` |
| Guest messages: consent only, same text, no incentives, STOP | `guests/review_requests.py` |
