"""Message templates for the review business. Plain text, no links in e-mails, no images, no tracking: what
reaches inboxes, not spam folders.

The language follows the campaign's country (country.py): English for the US, UK and Australia, German for
Germany. Every template can be replaced in the config ([outreach.email], [outreach.whatsapp],
[outreach.letters], [outreach.hooks]).

Placeholders: {greeting} {business} {first_name} {first_name_or_team} {audience} {place} {hook} {usp} {intro}
{offer} {demo_link} {sender_name} {sender_first} {sender_business} {sender_phone} {sender_city}
{sender_address} {sender_website} {footer} {source_line}

What the messages promise has to stay true to the product and to Google's review rules: every guest is asked
the same way, nothing is offered in return for a review, and nobody is pushed (see docs/COMPLIANCE.md).
"""
from __future__ import annotations

import hashlib
import re
import string
from urllib.parse import quote

# ---------------------------------------------------------------------------------------------------------------
# English (US, UK, Australia)
# ---------------------------------------------------------------------------------------------------------------
EN = {
    # Short (about 110 words), personal first line, one easy question to answer, no links (better delivery).
    "subjects": [
        "Google reviews for {business}",
        "{business} on Google Maps",
        "quick idea for {business}",
    ],
    "first": """{greeting}

{intro} {hook}

That's what we fix: a small QR + tap stand on your tables opens your Google review page in one tap, right before guests pay. Google counts reviews and rating in its local ranking, so more reviews help {business} show up higher on Google Maps.

{offer} {attachment_note}

Want a free preview page with your name on it? Just reply "yes".

Thanks,
{sender_name}
{footer}""",
    "follow_ups": [
        """{greeting}

A quick follow-up on my note about Google reviews for {business}. Guests need no app, everyone is asked the same way (fully within Google's rules), and it's a one-time price, no subscription.

Want me to send a free preview with your name on it? A one-word "yes" is enough.

{sender_name}
{footer}""",
        """{greeting}

Last note from me, promise. If more Google reviews for {business} become a priority, just reply "yes" and I'll send you a free preview page. Either way, thanks for reading.

All the best,
{sender_name}
{footer}""",
    ],
    "footer": """{sender_business}
{sender_address}
WhatsApp/phone: {sender_phone}

{source_line}
Not interested? Just reply "no" and we won't write again.""",
    "source_line": "We found this address on your website or public listing; reply \"delete\" and we erase it.",
    "offer": "It's a one-time price from $99, no monthly fees.",
    "attachment_note": "I've attached a two-page overview (PDF) with pictures of how it works.",
    "intro_usp": 'I came across {business} and liked this line on your website: "{usp}".',
    "intro_plain": "I came across {business} while looking at {audience} in {place}.",
    "greeting_named": "Hi {first_name},",
    "greeting_team": "Hello {business} team,",
    "whatsapp_cold": ("Hi {business} team, I'm {sender_first} from {sender_business}. We help {audience} get more Google reviews "
                      "with a simple, Google-compliant QR/tap stand. Could I send you a free preview? If you'd rather not "
                      "get messages from us, just reply STOP."),
    "whatsapp_opted_in": ("Hi {first_name_or_team}, this is {sender_first} from {sender_business} - thanks for your reply! "
                          "Here is the free preview for {business}: {demo_link} Happy to answer any questions here."),
    "letter": """{greeting}

Many happy guests would leave a review - they just don't think of it. We set up a small QR and tap (NFC) stand for the tables and the counter at {business}: one scan opens your Google review page. If you take payments by link (PayPal, Square, Stripe, SumUp), your payment link sits right next to it.

- No app, no discounts or prize draws: every guest is asked the same way, as Google requires.
- {offer}
- We can change the link at any time without reprinting the stands.

See a free preview for {business}: {demo_link}
Or message us on WhatsApp: {sender_phone}

Kind regards,
{sender_name}
{sender_business}
{sender_address}

Don't want to hear from us? A short message is enough and we delete your details. We found your business details in public sources (your website, OpenStreetMap, Overture Maps).""",
    "letter_greeting_named": "Dear {person},",
    "letter_greeting_team": "Dear {business} team,",
}

HOOKS_EN = {
    "restaurant": "Most people pick where to eat by star rating and recent reviews, yet most happy guests never leave one.",
    "cafe": "Regulars love a good cafe but rarely think of reviewing it.",
    "bar": "People check recent reviews before picking a bar, and happy guests rarely leave one.",
    "bakery": "Bakeries live on regulars, and their reviews are the best advert for new customers nearby.",
    "salon": "Clients pick salons by recent reviews, and the best moment to ask is right after the appointment.",
    "gym": "People compare gyms on Google before signing up; happy members' reviews are your best advert.",
    "hotel": "Guests compare places by their newest reviews, and checkout is when they are happiest to help.",
    "dental": "Patients read reviews before they book, and a neutral request to every patient keeps it fair.",
    "auto": "Drivers pick a garage by its reviews, and customers are happiest when they collect their car.",
    "health": "Patients compare clinics by their Google reviews before they book, and most happy patients never write one.",
    "pets": "Pet owners choose groomers and vets almost entirely by reviews, and happy owners rarely leave one.",
    "tattoo": "People choose a studio by its portfolio and its reviews, and happy clients rarely write one.",
    "entertainment": "Groups pick where to go out by recent reviews, and happy guests rarely leave one.",
    "retail": "Shoppers check reviews before visiting a local shop, and happy customers rarely leave one.",
    "laundry": "People pick a laundromat or dry cleaner nearby by its reviews, and regulars rarely write one.",
    "default": "Customers check Google reviews before they visit, and most happy customers never leave one.",
}
AUDIENCE_EN = {
    "restaurant": "restaurants", "cafe": "cafes", "bar": "bars and pubs", "bakery": "bakeries and ice-cream shops",
    "salon": "salons and barbers", "gym": "gyms and studios", "hotel": "hotels and guesthouses",
    "dental": "dental practices", "auto": "garages and car washes", "health": "clinics and med spas",
    "pets": "pet groomers and vets", "tattoo": "tattoo studios", "entertainment": "entertainment venues",
    "retail": "local shops", "laundry": "laundromats and dry cleaners", "default": "local businesses",
}

# ---------------------------------------------------------------------------------------------------------------
# German (Germany). Cold e-mail is not allowed there (UWG §7): e-mails go only to businesses that asked for
# information (Status "Opted in" or a reply); the first contact is a letter.
# ---------------------------------------------------------------------------------------------------------------
DE = {
    "subjects": [
        "Ihre Vorschau: mehr Google-Bewertungen für {business}",
        "{business}: Google-Bewertungen - wie besprochen",
    ],
    "first": """{greeting}

vielen Dank für Ihr Interesse. Wie versprochen hier kurz, wie es funktioniert:

Wir richten für {business} kleine QR- und NFC-Aufsteller für Tische und Theke ein. Ein Scan oder Antippen öffnet Ihre Google-Bewertungsseite. Wenn Sie Zahlungen per Link annehmen (PayPal, SumUp, Stripe), steht Ihr Zahlungslink direkt daneben. Ohne App, ohne Rabatte oder Gewinnspiele - jeder Gast wird gleich gefragt, so wie Google es verlangt.

{offer}

Soll ich Ihnen eine kostenlose Vorschau für {business} schicken? Eine kurze Antwort mit "Ja" genügt.

Viele Grüße
{sender_name}
{footer}""",
    "follow_ups": [
        """{greeting}

ich wollte kurz nachfragen, ob die Vorschau für {business} noch interessant ist. Ein "Ja" genügt.

Viele Grüße
{sender_name}
{footer}""",
    ],
    "footer": """{sender_business}
{sender_address}
{sender_phone}

{source_line}
Kein Interesse mehr? Antworten Sie einfach mit "Nein" - dann melden wir uns nicht wieder.""",
    "source_line": "Ihre Kontaktdaten nutzen wir nur für diese Anfrage; mit \"Löschen\" entfernen wir sie.",
    "offer": "Einmalige Einrichtung, kein Abo.",
    "intro_usp": "",
    "intro_plain": "",
    "greeting_named": "Guten Tag {first_name},",
    "greeting_team": "Guten Tag,",
    "whatsapp_cold": "",
    "whatsapp_opted_in": ("Hallo {first_name_or_team}, hier ist {sender_first} von {sender_business} - danke für Ihre Nachricht! "
                          "Hier die kostenlose Vorschau für {business}: {demo_link} Fragen beantworte ich gern hier."),
    "letter": """Mehr Google-Bewertungen für {business} - fair und nach Google-Richtlinien

{greeting}

viele zufriedene Gäste würden gern eine Bewertung schreiben - sie denken nur nicht daran. Wir richten für {business} kleine QR- und NFC-Aufsteller für Tische und Theke ein: Ein Scan, und Ihre Google-Bewertungsseite öffnet sich. Wenn Sie Zahlungen per Link annehmen (PayPal, SumUp, Stripe), steht Ihr Zahlungslink gleich daneben.

- Ohne App, ohne Rabatte oder Gewinnspiele: Jeder Gast wird gleich gefragt, so wie Google es verlangt.
- {offer}
- Den Link können wir jederzeit ändern, ohne neue Aufsteller zu drucken.

Ihre kostenlose Vorschau: {demo_link}
Oder schreiben Sie uns per WhatsApp: {sender_phone}

Mit freundlichen Grüßen
{sender_name}
{sender_business}
{sender_address}

Keine Post mehr von uns? Eine kurze Nachricht genügt, dann löschen wir Ihre Daten. Ihre Geschäftsdaten stammen aus öffentlichen Quellen (Ihre Website, OpenStreetMap, Overture Maps).""",
    "letter_greeting_named": "Guten Tag {person},",
    "letter_greeting_team": "Guten Tag,",
}

HOOKS_DE = {"default": ""}
AUDIENCE_DE = {
    "restaurant": "Restaurants", "cafe": "Cafés", "bar": "Bars und Kneipen", "bakery": "Bäckereien und Eiscafés",
    "salon": "Friseure und Kosmetikstudios", "gym": "Fitnessstudios", "hotel": "Hotels und Pensionen",
    "dental": "Zahnarztpraxen", "auto": "Werkstätten und Waschanlagen", "default": "lokale Geschäfte",
}

LANGS = {"en": (EN, HOOKS_EN, AUDIENCE_EN), "de": (DE, HOOKS_DE, AUDIENCE_DE)}

PLACEHOLDERS = {"greeting", "business", "first_name", "first_name_or_team", "audience", "place", "hook", "usp", "intro",
                "offer", "demo_link", "sender_name", "sender_first", "sender_business", "sender_phone", "sender_city",
                "sender_address", "sender_website", "footer", "source_line", "person", "attachment_note"}

# The templates the rest of the code (and the config validation) refers to, in the default language.
SUBJECTS = EN["subjects"]
FIRST_EMAIL = EN["first"]
FOLLOW_UPS = EN["follow_ups"]
WHATSAPP_COLD = EN["whatsapp_cold"]
WHATSAPP_OPTED_IN = EN["whatsapp_opted_in"]
HOOKS = HOOKS_EN
AUDIENCE = AUDIENCE_EN


def texts(lang: str = "") -> dict:
    """The template set for a language ('' = the active country's)."""
    if not lang:
        from .. import country

        lang = country.active().language
    return LANGS.get(lang, LANGS["en"])[0]


def unknown_placeholders(template: str) -> set[str]:
    names = {f for _, f, _, _ in string.Formatter().parse(template) if f}
    return names - PLACEHOLDERS


class _Keep(dict):
    def __missing__(self, key):          # leave unknown {placeholders} visible instead of crashing
        return "{" + key + "}"


def render(template: str, ctx: dict) -> str:
    text = template.format_map(_Keep(ctx))
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def pick(options: list[str], seed: str) -> str:
    """Deterministic choice per lead, so a lead always gets the same variant (and copies vary across leads)."""
    if not options:
        return ""
    h = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16)
    return options[h % len(options)]


def demo_link(oc: dict, business: str, lang: str) -> str:
    base = str(oc.get("demo_url") or "").strip()
    if not base:
        return ""
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}n={quote(business or '', safe='')}&lang={lang}"


def context(lead, oc: dict, lang: str = "") -> dict:
    """Template values for one lead. oc = cfg["outreach"]."""
    from .. import country

    lang = lang or country.active().language
    t, hooks_base, audience_base = LANGS.get(lang, LANGS["en"])
    s = oc["sender"]
    hooks = {**hooks_base, **(oc.get("hooks") or {})}
    audience = {**audience_base, **(oc.get("audience") or {})}
    sender_name = s.get("name", "").strip()
    first = lead.first_name
    person = re.sub(r"\(.*?\)", "", (getattr(lead, "person", "") or "").split("\n")[0]).strip()
    group = category_group(getattr(lead, "category_key", ""))
    ctx = {
        "business": lead.business,
        "first_name": first,
        "first_name_or_team": first or ("Team" if lang == "de" else "there"),
        "audience": audience.get(group) or audience.get(lead.category_key) or audience["default"],
        "place": lead.area or s.get("city", ""),
        "sender_name": sender_name,
        "sender_first": sender_name.split(" ")[0] if sender_name else "",
        "sender_business": s.get("business", "").strip(),
        "sender_phone": s.get("phone", "").strip(),
        "sender_city": s.get("city", "").strip(),
        "sender_address": s.get("postal_address", "").strip(),
        "sender_website": s.get("website", "").strip(),
        "person": person,
        "offer": str(oc.get("offer") or "").strip() or t["offer"],
        "demo_link": demo_link(oc, lead.business, lang),
        "attachment_note": "",       # set by the engine when the e-mail carries the PDF
    }
    ctx["greeting"] = render(t["greeting_named"] if first else t["greeting_team"], ctx)
    ctx["hook"] = render(hooks.get(group) or hooks.get(lead.category_key) or hooks.get("default", ""), ctx)
    usp = re.sub(r"\s+", " ", getattr(lead, "usp", "") or "").strip().rstrip(".!?").replace('"', "'")
    ctx["usp"] = usp
    ctx["intro"] = render(t["intro_usp"] if usp and t["intro_usp"] else t["intro_plain"], ctx)
    ctx["source_line"] = render(t["source_line"], ctx) if t.get("source_line") else ""
    ctx["footer"] = render(t["footer"], ctx)
    return ctx


def letter_context(lead, oc: dict, lang: str = "") -> dict:
    from .. import country

    lang = lang or country.active().language
    t = texts(lang)
    ctx = context(lead, oc, lang)
    ctx["greeting"] = render(t["letter_greeting_named"] if ctx["person"] else t["letter_greeting_team"], ctx)
    return ctx


# Our categories -> the message's wording group (categories differ per campaign config).
_GROUPS = {"restaurant": ("restaurant", "fast_food", "takeaway"), "cafe": ("cafe", "coffee"), "bar": ("bar", "pub"),
           "bakery": ("bakery", "ice_cream", "dessert"), "salon": ("salon", "barber", "beauty", "nail", "spa", "hair"),
           "gym": ("gym", "fitness", "yoga", "studio"), "hotel": ("hotel", "guest", "bnb", "hostel"),
           "dental": ("dental", "dentist"), "auto": ("auto", "garage", "car_wash", "car"),
           "health": ("health", "chiro", "medspa", "clinic"), "pets": ("pet", "vet", "groom"), "tattoo": ("tattoo",),
           "entertainment": ("entertain", "bowling", "arcade", "escape"), "retail": ("retail", "boutique", "florist", "gift"),
           "laundry": ("laundry", "laundromat")}


def category_group(key: str) -> str:
    k = (key or "").lower()
    for group, words in _GROUPS.items():
        if any(w in k for w in words):
            return group
    return "default"
