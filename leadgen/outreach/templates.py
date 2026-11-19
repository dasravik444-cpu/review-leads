"""Message templates for the review business. Plain text, no links in e-mails, no images, no tracking: what
reaches inboxes, not spam folders.

The language follows the campaign's country (country.py): English for the US, UK and Australia, German for
Germany. Every template can be replaced in the config ([outreach.email], [outreach.whatsapp],
[outreach.letters], [outreach.hooks]).

Placeholders: {greeting} {business} {first_name} {first_name_or_team} {audience} {place} {hook} {usp} {intro}
{offer} {demo_link} {sender_name} {sender_first} {sender_business} {sender_phone} {sender_city}
{sender_address} {sender_website} {footer} {source_line}. A campaign can have its own footer ([outreach.email] footer).

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

That's what we fix: a QR code on your tables, counter and receipts opens your Google review page in one scan. Google counts reviews and rating in its local ranking, so more reviews help {business} show up higher on Google Maps, and they show new customers you can be trusted.

{offer} {attachment_note}

Want a free preview page with your name on it? Just reply "yes".

Thanks,
{sender_name}
{footer}""",
    "follow_ups": [
        """{greeting}

A quick follow-up on my note about Google reviews for {business}. Guests need no app, everyone is asked the same way (fully within Google's rules), and we track your new reviews for you every month.

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
    "offer": "We also track your new Google reviews every month.",
    "attachment_note": "I've attached a two-page overview (PDF) with pictures of how it works.",
    "attachment_note_two": ("I've attached two short overviews (PDF): how we grow your Google reviews, and how we "
                            "bring past customers back."),
    "intro_usp": 'I came across {business} and liked this line on your website: "{usp}".',
    "intro_plain": "I came across {business} while looking at {audience} in {place}.",
    "greeting_named": "Hi {first_name},",
    "greeting_team": "Hello {business} team,",
    "whatsapp_cold": ("Hi {business} team, I'm {sender_first} from {sender_business}. We help {audience} get more Google reviews "
                      "with a simple, Google-compliant QR code. Could I send you a free preview? If you'd rather not "
                      "get messages from us, just reply STOP."),
    # The ending of a WhatsApp message that uses the first e-mail's words ([outreach.whatsapp] same_as_email).
    "whatsapp_footer": """{sender_business}

Not interested? Just reply STOP and we won't message you again.""",
    "whatsapp_opted_in": ("Hi {first_name_or_team}, this is {sender_first} from {sender_business} - thanks for your reply! "
                          "Here is the free preview for {business}: {demo_link} Happy to answer any questions here."),
    "letter": """{greeting}

Many happy guests would leave a review - they just don't think of it. We make a QR code for the tables, the counter and the receipts at {business}: one scan opens your Google review page. You print it yourself, as often as you like.

- No app, no discounts or prize draws: every guest is asked the same way, as Google requires.
- {offer}
- We track your new Google reviews and send you a short report every month.

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

Wir erstellen für {business} einen QR-Code für Tische, Theke und Kassenbon. Ein Scan öffnet Ihre Google-Bewertungsseite. Ohne App, ohne Rabatte oder Gewinnspiele - jeder Gast wird gleich gefragt, so wie Google es verlangt.

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

viele zufriedene Gäste würden gern eine Bewertung schreiben - sie denken nur nicht daran. Wir erstellen für {business} einen QR-Code für Tische, Theke und Kassenbon: Ein Scan, und Ihre Google-Bewertungsseite öffnet sich. Sie drucken ihn selbst, so oft Sie möchten.

- Ohne App, ohne Rabatte oder Gewinnspiele: Jeder Gast wird gleich gefragt, so wie Google es verlangt.
- {offer}
- Wir verfolgen Ihre neuen Google-Bewertungen und schicken Ihnen jeden Monat einen kurzen Bericht.

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

# ------------------------------------------------------------------------------------------------------------------
# The wording of Aurenflow International (the worldreach repository, worldreach/outreach/templates.py), taken over
# for India on 19 November 2026: per kind of business what goes wrong (pain), what we do (what), an example sum
# (math, always "if"), the topic and the subjects. Each business gets the same variant every time (by its key), two
# businesses rarely the same. Used through the placeholders {pain} {what} {math} {topic} {people} {cta} {cta2}
# {group_subject} (config/in/_base.toml [outreach.email] first, follow_ups and subjects).
GROWTH: dict[str, dict] = {
    "fitness": {
        "audience": "gyms and studios", "people": "members", "topic": "winning back past members",
        "subjects": ["past members of {business}", "{business}: members who stopped coming",
                     "a question about {business}"],
        "pain": ["Most gyms and studios have a list of members who quietly stopped coming, and nobody has the time to "
                 "write to each of them.",
                 "Every studio has members who meant to come back and never did, and a failed payment often ends a "
                 "membership without anyone noticing."],
        "what": "We do that follow-up for you: a short, friendly message series to past members, polite reminders "
                "when a payment fails, and a Google review request to members who are happy. It runs from your own "
                "member list, and there is nothing to install.",
        "math": "if {business} has 300 past members and only 5 in 100 come back, that is 15 memberships from people "
                "who already know you",
    },
    "martial": {
        "audience": "martial arts schools", "people": "students", "topic": "bringing back past students",
        "subjects": ["past students of {business}", "{business}: students who stopped training",
                     "a question about {business}"],
        "pain": ["Most schools have a list of students who stopped training after a few months, and parents who "
                 "meant to renew and forgot.",
                 "Every school loses students between belts, and unpaid fees are awkward to chase in person."],
        "what": "We do that follow-up for you: a friendly message series to past students and their parents, polite "
                "reminders for unpaid fees, and a Google review request to happy families. It runs from your own "
                "student list, and there is nothing to install.",
        "math": "if {business} has 200 past students and only 5 in 100 return, that is 10 students back on the mat",
    },
    "salon": {
        "audience": "salons and spas", "people": "clients", "topic": "bringing back clients who are overdue",
        "subjects": ["clients of {business} who are overdue", "{business}: empty chairs", "a question about {business}"],
        "pain": ["Most salons have clients who were happy, meant to rebook and simply never got round to it.",
                 "A client who is two weeks overdue rarely calls; usually it only takes one friendly reminder."],
        "what": "We send that reminder for you: a short message when a client is due for the next visit, a friendly "
                "series to the ones who have not been in for months, and a Google review request after a good "
                "appointment. It runs from your own client list, and there is nothing to install.",
        "math": "if {business} has 400 clients who have not been in for three months and 8 in 100 rebook, that is 32 "
                "appointments from people who already like you",
    },
    "food": {
        "audience": "restaurants and cafes", "people": "guests", "topic": "bringing past guests back",
        "subjects": ["past guests of {business}", "{business}: guests who came once", "a question about {business}"],
        "pain": ["Most restaurants have hundreds of guests in their booking and ordering lists who came once, liked "
                 "it, and were never invited back.",
                 "A first visit is the expensive one to win; the second usually only needs an invitation."],
        "what": "We send that invitation for you: a friendly note to guests who have not been back in a while, a "
                "thank-you with a Google review request after a visit, and a reminder before the dates that matter "
                "to you. It runs from the guest list you already have, and there is nothing to install.",
        "math": "if {business} has 1,000 past guests on its lists and 4 in 100 book again, that is 40 tables from "
                "people who already know the food",
    },
    "hotel": {
        "audience": "hotels and guesthouses", "people": "guests", "topic": "direct rebookings and reviews",
        "subjects": ["past guests of {business}", "{business}: direct bookings from past guests",
                     "a question about {business}"],
        "pain": ["Most guests who enjoyed their stay would come back or leave a review, but once they have checked "
                 "out nobody writes to them.",
                 "Past guests are the cheapest bookings a hotel can get, and they usually return through a booking "
                 "site that takes its commission."],
        "what": "We do that follow-up for you: a thank-you with a Google review request after checkout, and an "
                "invitation to past guests to book direct for their next stay. It runs from your own guest list, "
                "and there is nothing to install.",
        "math": "if {business} writes to 500 past guests and 3 in 100 book direct, that is 15 stays without a "
                "booking-site commission",
    },
    "pets": {
        "audience": "groomers and pet services", "people": "clients", "topic": "rebooking clients who are overdue",
        "subjects": ["clients of {business} who are overdue", "{business}: rebooking reminders",
                     "a question about {business}"],
        "pain": ["Most pet owners mean to rebook every six weeks and remember after ten.",
                 "Owners who were happy rarely leave a review or rebook on time unless someone reminds them."],
        "what": "We send that reminder for you: a short message when a pet is due again, a friendly series to "
                "clients who have not been back, and a Google review request after a visit. It runs from your own "
                "client list, and there is nothing to install.",
        "math": "if {business} has 300 clients who are overdue and 10 in 100 rebook, that is 30 appointments",
    },
    "auto": {
        "audience": "garages and detailers", "people": "customers", "topic": "service reminders and reviews",
        "subjects": ["customers of {business} who are due", "{business}: service reminders",
                     "a question about {business}"],
        "pain": ["Most drivers forget when the next service is due, and go wherever is nearest on the day they "
                 "remember.",
                 "Customers are happiest on the day they collect the car, and almost nobody asks them for a review "
                 "then."],
        "what": "We do that follow-up for you: a reminder when a customer is due again, a friendly note to the ones "
                "who have not been back in a year, and a Google review request after each job. It runs from your "
                "own customer list, and there is nothing to install.",
        "math": "if {business} has 600 customers who are due and 5 in 100 book, that is 30 jobs",
    },
    "default": {
        "audience": "local businesses", "people": "customers", "topic": "bringing past customers back",
        "subjects": ["past customers of {business}", "{business}: customers who came once",
                     "a question about {business}"],
        "pain": ["Most local businesses have a list of customers who were happy and simply never came back, and "
                 "nobody has the time to write to each of them.",
                 "Winning a new customer is expensive; a past customer usually only needs a friendly reminder."],
        "what": "We do that follow-up for you: a friendly message series to past customers, a reminder when someone "
                "is due again, and a Google review request to the happy ones. It runs from your own customer list, "
                "and there is nothing to install.",
        "math": "if {business} has 500 past customers and 5 in 100 come back, that is 25 sales from people who "
                "already know you",
    },
}

# Our category keys (config/shared/categories.toml) -> the wording group.
_GROWTH_WORDS = {
    "martial": ("martial", "karate", "judo", "taekwondo", "jiu"),
    "fitness": ("gym", "fitness", "yoga", "pilates", "studio", "dance", "crossfit", "boxing", "climb", "swim"),
    "salon": ("salon", "barber", "beauty", "nail", "spa", "hair", "tattoo", "massage", "lash", "brow"),
    "food": ("restaurant", "cafe", "coffee", "bar", "pub", "bakery", "ice_cream", "dessert", "food"),
    "hotel": ("hotel", "guest", "bnb", "hostel", "motel", "inn", "resort", "lodg"),
    "pets": ("pet", "vet", "groom", "kennel"),
    "auto": ("auto", "garage", "car_wash", "car", "detail", "tire"),
}



GROWTH_CTA = ['Would it be worth a quick chat? A one-word "yes" is enough.',
              'Shall I send you a free preview with your name on it? Just reply "yes".',
              'Would a free preview for {business} be useful? A reply with "yes" is all it takes.']
GROWTH_CTA2 = ['Shall I send you a free preview with {business}\'s name on it? A "yes" is enough.',
               'Would you like a free preview for {business}? Just reply "yes".']


def growth_group(key: str) -> str:
    k = (key or "").lower()
    for group, words in _GROWTH_WORDS.items():
        if any(w in k for w in words):
            return group
    return "default"


PLACEHOLDERS = {"greeting", "business", "first_name", "first_name_or_team", "audience", "place", "hook", "usp", "intro",
                "offer", "demo_link", "sender_name", "sender_first", "sender_business", "sender_phone", "sender_city",
                "sender_address", "sender_website", "footer", "source_line", "person", "attachment_note",
                "pain", "what", "math", "topic", "people", "cta", "cta2", "group_subject"}

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
        "sender_address": tidy_address(s.get("postal_address", "")),
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
    g = GROWTH[growth_group(getattr(lead, "category_key", "") or getattr(lead, "category_label", ""))]
    seed = lead.key or lead.business
    ctx.update(people=g["people"], topic=g["topic"])
    ctx["pain"] = render(pick(g["pain"], seed + ":pain"), ctx)
    ctx["what"] = render(g["what"], ctx)
    ctx["math"] = render(g["math"], ctx)
    ctx["cta"] = render(pick(GROWTH_CTA, seed + ":cta"), ctx)
    ctx["cta2"] = render(pick(GROWTH_CTA2, seed + ":cta2"), ctx)
    ctx["group_subject"] = render(pick(g["subjects"], seed + ":subject"), ctx)
    ctx["footer"] = render((oc.get("email") or {}).get("footer") or t["footer"], ctx)
    return ctx


def tidy_address(text: str) -> str:
    """The postal address as typed in the settings, written tidily: single spaces, ", " between parts, and
    capital letters when it was typed all in small letters ("daspara, rishra , west bengal" -> "Daspara, Rishra,
    West Bengal")."""
    lines = [re.sub(r"\s*,\s*", ", ", re.sub(r"[ \t]+", " ", line)).strip(" ,") for line in (text or "").splitlines()]
    out = "\n".join(line for line in lines if line)
    return string.capwords(out, " ") if out == out.lower() and "\n" not in out else out


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
