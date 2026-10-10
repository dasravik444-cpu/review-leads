# The business: Google review QR codes for restaurants, cafés and salons

Research and recommendations, 8 October 2026. Prices and figures are from the sources linked. Check them before
you quote them to a customer.

## 1. Why businesses pay for reviews

Local customers choose by star rating and by how recent the reviews are. BrightLocal's 2026 survey of US
consumers found:

- 97% read reviews when looking at local businesses.
- 31% only consider businesses rated 4.5 stars or more, up from 17% a year earlier.
- About three in four want reviews from the last three months.
- Four in five prefer businesses that answer all their reviews.
- Google is still the main review site (71%), though falling.
- In the last survey with an industry breakdown (2020), **restaurants** were the most-read category, ahead of
  hotels and medical.

Sources: [BrightLocal 2026 via PinMeTo](https://www.pinmeto.com/news/brightlocal-local-consumer-review-survey-2026/),
[BrightLocal survey](https://www.brightlocal.com/research/local-consumer-review-survey/),
[BrightLocal 2020](https://www.brightlocal.com/research/local-consumer-review-survey-2020/).

The problem every owner knows: most happy guests never write a review, while unhappy ones often do. A steady,
fair stream of reviews from ordinary guests is the fix, and that is what we sell.

## 2. The product

1. **QR + NFC stands** for the tables and the counter. A guest scans or taps once.
2. **The page behind the stand** (`site/`), one per customer, in German and English:
   - *Pay the bill* (their PayPal, SumUp, Stripe or Square link) and *Write a Google review*, side by side.
   - Optionally *See the menu*.
   - The review opens next to the page. When the guest comes back, the page shows the pay button as the next step.
3. **Changes without reprinting.** The stand points to our page, not to Google. If the payment provider, the
   menu or the review link changes, we change one file.
4. **Optional: WhatsApp review requests** to guests who agreed, after their visit (`guests/`). This has a free
   one-tap mode and a paid automatic mode.
5. **Fair by design.** Every guest is asked the same way, with nothing in return and no pre-filtering
   (docs/COMPLIANCE.md). Several pay-at-table apps send only 5-star raters to Google. That is "review gating",
   which Google bans and which can cost a restaurant its reviews. Our way is a selling point.

### Why not "QR → Google review → back to the payment app"?

Your option 1 is technically impossible and also against the rules:

- **Google's review form has no "return to" address.** After posting, the guest stays on Google. No QR code or
  link can make Google send them on to PayPal.
- **A review before paying is pressure on the premises.** That is exactly what Google's policy forbids ("require
  or pressure users to leave ratings or write reviews while on the premises"). A review must never stand between
  a guest and their bill.

So the page offers both. Pay comes first, and the review is optional. The review opens beside the page, and the
page waits with the pay button highlighted. If the customer uses **Stripe or Square payment links**, the reverse
also works: pay first, then the provider sends the guest back to our thank-you page with the review button
(`/r/<id>/thanks.html`). Stripe documents this ([Stripe: after the payment](https://docs.stripe.com/payment-links/post-payment)).
Square has a redirect setting for payment links, according to its community forum. SumUp's API checkout has a
`redirect_url` ([SumUp hosted checkout](https://developer.sumup.com/online-payments/checkouts/hosted-checkout/)).
PayPal.me links do not return.

### The payment reality in Germany

Most restaurants take cards at the table or the counter:

- 89% of German venues that list payment options on Google Maps accept cards (DSGV, September 2026).
- Cards are now about 46% of restaurant sales, cash about 44% (girocard/infas).

So for full-service restaurants the stand is mainly a **review stand** (with a menu link). The pay button matters
most for cafés, takeaways, food trucks, salons and market stalls that already use PayPal, SumUp or Stripe links.
Sources: [it-finanzmagazin](https://www.it-finanzmagazin.de/?p=250275),
[Tageskarte](https://www.tageskarte.io/technologie/detail/neue-studie-immer-mehr-gastronomen-setzen-auf-kartenzahlung.html).

## 3. Price and packages

**Decided 10 October 2026 (brand: Qrated):** two one-time packages, and nothing is shipped. Stands can't be sent
from India to the US or Europe at a sensible cost, so the business gets its QR code as print-ready files and prints
it itself. Prices in US dollars, paid by card or PayPal; the same in other English-speaking markets:

| Package | What they get | Price |
|---|---|---|
| **Starter** | Their QR code, linked straight to their Google review page; print-ready QR designs for tables, counter, window and receipts; review tracking: a report of new reviews and rating every month for 12 months | $100 |
| **Pro** | Starter + review requests to their own customer list by WhatsApp and e-mail (up to 3 reminders), with their Google review link or a short feedback form | $200 |

Paid WhatsApp sending (Meta's WhatsApp Business Platform) is passed on at cost if a customer wants it fully
automatic; Meta's price per message differs by country, about €0.11 in Germany. Review tracking needs the
business's Google rating and review count once a month: from Google Maps by hand, or from the Google Places API
(free monthly allowance; needs a Google Cloud billing account).

The earlier plan (below, kept for the research) had acrylic NFC stands; it was dropped for the reason above.

**Your costs per customer.**

- Hosting is free: on Cloudflare's free plan, requests for static pages are free and unlimited.
- A single NFC stand sells for about €11–34 on eBay.de. Blank NFC cards cost $0.18–0.50 each from wholesalers,
  with minimum orders of 50–100 ([NFC stand price research](#sources-for-section-3-and-4)).
- Don't ship from India for every order. Postage is slow and expensive, and import duties apply. Use a print
  service in the customer's country (US print-on-demand or Etsy/Amazon sellers who print and ship NFC stands),
  or send the **Digital** package, which has nothing to ship.
- A blank stand plus an NFC sticker (programmed with the free *NFC Tools* app) plus a printed QR is cheapest. A
  printed acrylic stand looks best.

## 4. Competitors

| Who | Price | Note |
|---|---|---|
| Birdeye | $299–449 per location per month | full reputation suite |
| Podium | $399–599 per month | messaging + payments + reviews |
| NiceJob | from $75 per month | review requests, no contract |
| ReviewPush / Rateo / Revyo | about $25–30 per month, Revyo €9.99 | restaurant review tools |
| eBay/Etsy NFC stands | €11–34 one-off | only a stand with Google's link, no page, no changes |

Our niche sits between a bare €15 stand and a €300 monthly suite:

- a one-time price;
- a QR code that opens the Google review page directly;
- review tracking and reminders to past customers;
- German and English;
- built within Google's rules.

Be honest with customers. Google gives every business a free review link and QR code. What we add is the
print-ready designs, the setup, the review tracking and the guest messages.

<a id="sources-for-section-3-and-4"></a>Sources: [CostBench: Birdeye](https://costbench.com/software/review-management/birdeye),
[CostBench: Birdeye vs Podium](https://costbench.com/compare/birdeye-vs-podium/),
[NiceJob pricing](https://get.nicejob.com:443/pricing),
[Cloudflare Workers static assets pricing](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/).
The NFC stand prices come from eBay.de and Etsy listings found in the research. They are asking prices, not
averages.

## 5. Who to sell to

**USA.** Measured with the open data for Austin, Texas (25 km), 8 October 2026: 90,566 places, **29% with an
e-mail address already in the open data**, before any website is read. The US groups that matter most:

| Group (Austin) | Places | With e-mail |
|---|---|---|
| Restaurants | 5,191 | 36% |
| Hair / beauty / nails / barbers | 3,484 | 51% |
| Garages / car washes / auto services | 2,030 | 41% |
| Dentists | 1,035 | 48% |
| Gyms | 688 | 48% |
| Pet services and vets | 589 | 59% |
| Hotels | 415 | 57% |

US businesses almost never publish a WhatsApp number (1 in the whole Austin area), so e-mail is the US channel.
WhatsApp matters in the UAE, the UK and Singapore.

The US fleet covers 30 cities (`config/us/fleet.toml`) and 15 business types (`config/us/_base.toml`).

**Germany (on hold).** Measured with the open data for Berlin (20 km), 8 October 2026: **38,572 businesses** in
the first six categories.

| Category | Businesses | Why |
|---|---|---|
| Restaurants (incl. takeaway) | 16,318 | most-read category, many guests per day |
| Hair / beauty / barber / nails | 8,458 | repeat customers, chosen almost only by reviews |
| Cafés | 4,523 | many guests, often pay by link |
| Bars / pubs | 3,729 | tourists choose by reviews |
| Gyms / studios | 2,835 | high value per customer |
| Bakeries / ice cream | 2,709 | very high footfall |

About 80% have a phone number in the open data and about 25% an e-mail. These figures were measured before the
category update of 8 October, which added massage and skin-care studios, fitness trainers and pizza delivery.

The categories live in `config/shared/categories.toml`. Hotels, dentists, garages, clinics, pet services,
tattoo studios, entertainment venues, boutiques and laundromats are switched on for the US.

## 6. How to reach them (by country)

The rules decide the channel (docs/COMPLIANCE.md):

- **Germany: no cold e-mail, WhatsApp or calls.** Use:
  1. **Letters.** The system writes 15 a day into the Letters tab, each with a personal preview link. Send them
     through an online letter service that prints and posts inside Germany (for example Pingen or LetterXpress,
     roughly €1 a letter including postage; check current prices). Test with 100 letters before scaling.
  2. **Inbound.** List the stands on eBay.de, Etsy and Amazon.de. Owners already search there for
     "Google Bewertung Aufsteller NFC". A product page that links to your preview is allowed.
  3. **Partners.** Agencies, web designers and menu printers in Germany sell to the same owners and may resell
     your stands.
- **UK:** e-mail limited companies, letters to sole traders. The system does both.
- **USA:** e-mail, with your postal address in every e-mail. This is the market where the existing e-mail engine
  works best.
- **Australia:** e-mail only to addresses the business publishes. Settle the open legal point in
  docs/COMPLIANCE.md first.

**Recommendation (your decision of 8 October): US first.** Cold e-mail is allowed there and costs nothing, the
open data already holds e-mails for a third of the businesses, and owners pay in dollars. Then the other
English-speaking markets: the UK, Ireland, Canada, Australia and New Zealand, and the UAE (WhatsApp) and
Singapore. Germany stays prepared (letters) for later.

## 7. Monthly running costs

| Item | Cost |
|---|---|
| GitHub (public repository) | $0, unlimited Actions minutes (docs/SETUP.md, step 1) |
| Google Sheet, Gmail, service account | $0 |
| Cloudflare Workers (customer pages) | $0 |
| WhatsApp Business app (one-tap messages) | $0 |
| Stands | per order (printed and shipped in the customer's country) |
| WhatsApp Business Platform (automatic guest messages, optional) | per message, by country |
| Germany only, later: letters about €1 each; a lawyer's one-off check of the letter | (estimate: a few hundred euros) |
