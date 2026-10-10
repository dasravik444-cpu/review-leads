# How Americans pay, and what Aurenflow's "Pay" button should open in the US

Research of 10 October 2026, for the QR page's pay step (site/). Figures are from the sources linked; check them
before quoting them to a customer.

## Cards first, cash third, QR still small

- **Cards dominate.** In the Federal Reserve's 2025 Diary of Consumer Payment Choice (2024 data), credit cards were
  35% and debit cards 30% of all consumer payments by number; cash was 14%, third for the fifth year running
  ([Federal Reserve FRBservices](https://www.frbservices.org/news/research/2025-findings-from-the-diary-of-consumer-payment-choice)).
- **Most in-person payments are card, cash or check.** QR payments exist but are still niche; the Fed's FedNow
  team gives CVS (PayPal and Venmo QR codes at select stores) as an example
  ([FedNow: QR codes and instant payments](https://frbservices.org/financial-services/fednow/instant-payments-education/qr-codes-and-instant-payments.html)).
  American Banker reported QR payments moving "from niche to partial mainstream" in 2025
  ([American Banker](https://www.americanbanker.com/payments/news/qr-code-payments-favored-to-gain-adoption-in-2025)).
- **No Google Pay QR in the US.** Google shut the Google Pay app in the US on 4 June 2024; Google Wallet only taps
  cards at the terminal ([Engadget](https://www.engadget.com/google-pay-is-shutting-down-in-the-us-later-this-year-105720968.html)).
- **Zelle lives only inside bank apps.** Its own app stopped on 1 April 2025; Zelle QR codes are shown in the
  banks' apps, so a web page cannot open a Zelle payment
  ([ABC/AP](https://abc30.com/amp/post/zelle-app-news-person-money-transferring-service-is-shutting-down-users-can-use-own-bank/16122687/)).

## Which payment apps Americans use

| App | Ever used (Pew, 2022) | Used in the past year (S&P Global, 2023) |
|---|---|---|
| PayPal | 57% | 64% |
| Venmo (owned by PayPal) | 38% | 28% |
| Zelle | 36% | 23% |
| Cash App | 26% | 23% |

Sources: [Pew Research](https://www.pewresearch.org/?p=8373),
[S&P Global Market Intelligence](https://www.spglobal.com/market-intelligence/en/news-insights/research/one-third-of-americans-use-three-or-more-financial-apps).
No newer survey of the same kind was found.

## Restaurants

Full-service restaurants mostly take cards at the table or counter. The big restaurant systems print their own pay
codes on the receipt, one per bill: Toast's payment QR (included with Toast's core plan,
[Toast](https://support.toasttab.com/en/article/Setting-up-mobile-payments-and-digital-menus)) and Square's
scan to pay (2.9% + 30¢, [Square](https://squareup.com/help/us/es/article/8184-beta-scan-to-pay)). A printed code on
a table cannot replace those, because each bill has its own.

## What this means for our page in the US

1. **Lead with reviews.** For a full-service restaurant the page offers the Google review, and the pay step says
   "pay at your table or the counter as usual" (site/ already does this for card-only businesses).
2. **Add the pay button where the business already takes app payments:** food trucks, cafés, takeaways, salons,
   barbers, market stalls. In this order: **PayPal / Venmo** (PayPal QR codes and links; most used), **Cash App**,
   **Square** payment links (if they use Square). The page already accepts paypal.me, venmo.com, cash.app and
   square.link addresses.
3. **Zelle:** only as text ("Zelle to name@email") with a copy button, since no web link opens it.
