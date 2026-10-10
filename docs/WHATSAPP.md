# WhatsApp for Aurenflow

What the WhatsApp side does, what it never does, and how to set it up on the tablet. Checked 10 October 2026.

## The rules that decide the design

- **WhatsApp bans numbers that send automated or bulk messages.** Its terms list "bulk messaging, auto-messaging,
  auto-dialing" as forbidden, and it finds them with machine learning and user reports
  ([WhatsApp Terms of Service](https://www.whatsapp.com/legal/terms-of-service)). A bot that messages the lead list
  by itself would get the new number banned within days, and the number with it.
- **Meta's official API sends no marketing messages to US numbers.** Since 1 April 2025, marketing template
  messages to +1 numbers fail, and the pause was still on in mid-2026
  ([Wati](https://www.wati.io/en/blog/whatsapp-marketing-messages-us-2026/),
  [Zoho](https://help.zoho.com/portal/es/community/topic/pausing-whatsapp-marketing-messages-for-us-numbers-starting-april-1-2025)).
  Replies to people who wrote first are free and allowed.
- **Businesses need people's agreement first.** Meta's rules require opt-in before a business messages someone, and
  a phone number alone is not opt-in
  ([Meta: Get opt-in for WhatsApp](https://developers.facebook.com/documentation/business-messaging/whatsapp/getting-opt-in)).
- **Few US businesses are on WhatsApp.** About a third of US adults use it (Pew 2025, via
  [Benton](https://benton.org/node/355990)). In Washington DC, 5 of 3,029 businesses publish a WhatsApp number; the
  other phone numbers are mostly shop and office lines, many of which are not on WhatsApp at all.

So: **e-mail does the cold outreach** (allowed, and automatic); **WhatsApp is for the few businesses that publish a
WhatsApp number, for people who say yes, and for everyone who writes to you first.**

## What the robot and the tablet do

1. **The robot fills the WhatsApp Queue tab** in your Google Sheet, with the message already written for each
   business:
   - businesses that publish a number as WhatsApp (on their website) and have no e-mail address, or whose e-mails
     got no answer;
   - leads who answered "yes" to an e-mail, at the top of the list, with the free-preview message.
   It starts at 5 a day and adds 5 every 7 days you actually sent, up to 20, because a new number that writes a
   lot of strangers is reported and banned. A number is never queued twice; "Not interested" or STOP puts it on
   the Do Not Contact list.
2. **You type `whatsapp` on the tablet** between about 8 PM and 2 AM India time on US working days (US office
   hours; a message at night looks like spam). For each message, WhatsApp Business opens with the text typed; you
   press Send, switch back to Termux and press Enter (or `n` = not on WhatsApp, `s` = skip, `q` = stop for now).
   The result goes into the Sheet, and the robot reads it on its next run.
3. **Later answers** (Replied, Interested, Not interested) you set in the Result column of the WhatsApp Queue tab,
   from the Sheets app on your phone.

`whatsapp list` only shows what is waiting.

## Set it up (once, about 30 minutes)

1. **The business profile** (WhatsApp Business → Settings → Business tools → Business profile):
   - Name: **Aurenflow**. Profile picture: `marketing/brand/aurenflow-icon.png` (the square logo).
   - Category: *Marketing Agency* (or *Business Service*).
   - Description: "More Google reviews for restaurants, cafés, salons and shops: a QR code that opens your Google
     review page in one scan. One-time price, no monthly fees."
   - E-mail: the business Gmail. Hours: when you answer (for example 8 PM - 3 AM India time = US office hours).
2. **WhatsApp Business on the tablet** (the `whatsapp` command opens chats there):
   - If the number's SIM is in another phone, use the tablet as a linked device: on the phone, WhatsApp Business →
     ⋮ → **Linked devices** → **Link a device**; on the tablet, install WhatsApp Business and choose
     **Link to existing account**, then scan the code shown with the phone.
   - Or register the number on the tablet itself.
3. **Only if the personal WhatsApp is also on the tablet:** make WhatsApp Business open WhatsApp links, so nothing
   goes out from your personal number. Android Settings → Apps → **WhatsApp** → **Open by default** → turn off
   *Open supported links*; then Apps → **WhatsApp Business** → **Open by default** → turn it on. (The command asks
   for WhatsApp Business by name anyway; this is the safety net.)
4. **Automatic messages in the app** (Business tools; free, and allowed because they answer people who wrote):
   - **Greeting message** (on, "Send to everyone"):
     "Hi, thanks for messaging Aurenflow! I'm Ravik. We help restaurants, cafés and salons get more Google
     reviews with a QR code that opens their Google review page in one scan. Want a free preview with your
     business's name on it? Just send me your business name and city."
   - **Away message** (on, outside business hours):
     "Thanks for your message! I'm away right now and will reply within a few hours. Ravik, Aurenflow"
   - **Quick replies** (type `/` in a chat to use them):
     - `/preview`: "Here's how it works: we make your QR code, it opens your Google review page, your customers
       scan it at the table or counter, and we send you a report of your new reviews every month. Send me your
       business name and city and I'll make you a free preview with your name on it."
     - `/price`: "Starter is $100, one time: your QR code linked to your Google review page, print-ready designs
       for tables, counter, window and receipts, and a monthly review report for 12 months. Pro is $200, one time:
       everything in Starter plus review requests to your customer list by WhatsApp and e-mail. No monthly fees."
     - `/pay`: "Here is the PayPal invoice: you can pay by card or PayPal. [paste the invoice link] Thank you!"
     - `/stop`: "Understood, I won't message you again. Sorry for the bother!" (then set the Result to
       *Not interested* in the Sheet)
   - **Labels**: New lead, Preview sent, Interested, Paid, Not interested.
5. **Your WhatsApp number in the settings** (it goes into the e-mail signature and your copy of the PDF): type
   `settings` and set `OUTREACH_SENDER_PHONE=+<country code and number>`, save (Ctrl+O, Enter, Ctrl+X).
6. **Every US working day**, 8 PM - 2 AM India time: `whatsapp`, and answer what comes back.

## Later: answers by a machine

When many people write to you, the official WhatsApp Business Platform can answer automatically (free for replies
to people who wrote first). It needs a Meta Business account, an approved app and a webhook; the same number can
stay on the WhatsApp Business app ("coexistence", through a Meta partner). Worth it only once chats are coming in
every day.
