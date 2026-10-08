"""Country rules: German websites, and who may be contacted how in Germany, the UK, Australia and the US
(docs/COMPLIANCE.md). Synthetic data only."""
from __future__ import annotations

import glob
from datetime import datetime
from zoneinfo import ZoneInfo

from conftest import make_config
from test_outreach import Clock, SmtpWorld, runner, sheet_with, status_of, tab

from leadgen import country
from leadgen.config import load_config
from leadgen.enrich.domains import candidate_domains, name_slugs
from leadgen.enrich.extract import extract_page
from leadgen.outreach.classify import classify_reply
from leadgen.outreach.engine import split_address
from leadgen.outreach.store import OutreachStore

SENDER = {"name": "Ravi Kumar", "business": "Review Studio", "phone": "+91 90000 00000", "city": "Kolkata",
          "postal_address": "12 Park Street, Kolkata 700016, India", "notify_email": "owner@example.com"}
PLACES = {
    "DE": ("Europe/Berlin", "Berlin", [52.52, 13.405]),
    "GB": ("Europe/London", "Manchester", [53.4808, -2.2426]),
    "AU": ("Australia/Melbourne", "Melbourne", [-37.8136, 144.9631]),
    "US": ("America/Chicago", "Austin", [30.2672, -97.7431]),
}


def country_cfg(code: str, sender=None, **email):
    tz, city, center = PLACES[code]
    return make_config(
        campaign={"country": code, "timezone": tz, "language": "de" if code == "DE" else "en", "region": code.lower(),
                  "lead_id_prefix": code},
        area={"name": city, "center": center, "radius_km": 3},
        outreach={"sender": SENDER if sender is None else sender,
                  "email": {"start_per_day": 5, "step": 0, "max_per_day": 40, "max_per_run": 8, **email},
                  "whatsapp": {"start_per_day": 2, "step": 0, "max_per_day": 2, "include_mobiles": False},
                  "letters": {"enabled": "auto", "per_day": 10}})


def wednesday_11(code: str) -> float:
    return datetime(2026, 10, 14, 11, 0, tzinfo=ZoneInfo(PLACES[code][0])).timestamp()   # a Wednesday


def row(n, name, **f):
    return {"Lead ID": f"T-{n:05d}", "Business Name": name, "Category": f.get("category", "Cafe"), "Area": "",
            "Address": f.get("address", ""), "Phones": f.get("phones", ""), "WhatsApp": "", "Emails": f.get("email", ""),
            "Priority": f.get("priority", "Medium"), "Contact Person": f.get("person", ""), "Key": f"key{n}",
            "Status": f.get("status", "New"), "Signals": f.get("signals", ""), "Legal Form": f.get("legal", ""),
            "Other Contacts (unverified)": f.get("unverified", "")}


def set_result(sess, tab_name, key, value):
    rows = sess.tabs[tab_name]["rows"]
    head = rows[0]
    for r in rows[1:]:
        if len(r) > head.index("Key") and r[head.index("Key")] == key:
            while len(r) <= head.index("Result"):
                r.append("")
            r[head.index("Result")] = value


# ------------------------------------------------------------------ German websites
IMPRESSUM = """<html><head><title>Impressum - Café Luise</title></head><body>
<h1>Impressum</h1><p>Angaben gemäß § 5 DDG</p>
<p>Café Luise GmbH<br>Inhaberin: Maria Müller-Schmidt<br>Kastanienallee 12<br>10435 Berlin</p>
<p>Telefon: 030 4405 1234<br>Telefax: 030 4405 1235<br>E-Mail: hallo@cafe-luise.de</p>
<p>Registergericht: Amtsgericht Charlottenburg, HRB 123456 B. USt-IdNr.: DE 123456789</p>
<p>Der Nutzung von im Rahmen der Impressumspflicht veröffentlichten Kontaktdaten zur Übersendung von nicht ausdrücklich
angeforderter Werbung und Informationsmaterialien wird hiermit ausdrücklich widersprochen.</p>
<p>Webdesign von Pixelwerk, info@pixelwerk.de, Tel. 030 9999999</p>
</body></html>"""


def test_german_impressum_gives_owner_phone_email_and_objection():
    country.use_country("DE", "Berlin")
    pe = extract_page(IMPRESSUM, "https://cafe-luise.de/impressum", region="DE", contact_page=True)
    found = {(f.kind, f.value) for f in pe.found}
    assert ("phone", "+493044051234") in found                      # Telefon
    assert ("phone", "+493044051235") not in found                  # Telefax is not a contact route
    assert ("email", "hallo@cafe-luise.de") in found
    assert ("email", "info@pixelwerk.de") not in found and ("phone", "+49309999999") not in found   # the web agency's
    assert ("person", "Maria Müller-Schmidt") in found              # Inhaberin, street not glued on
    assert ("legal_form", "GmbH/UG/AG") in found
    assert ("signal", "Objects to advertising (website notice)") in found
    assert not any(k == "phone" and v.endswith("123456") for k, v in found)   # register numbers are not phones


def test_german_names_give_german_domains_and_postcodes():
    country.use_country("DE", "Berlin")
    assert "cafemueller" in name_slugs("Café Müller")                # how Germans write umlauts in domains
    doms = candidate_domains("Café Müller GmbH", "berlin")
    assert "cafemueller.de" in doms and "cafemuellerberlin.de" in doms and not any(d.endswith(".co.in") for d in doms)
    assert country.postcodes("Kastanienallee 12, 10435 Berlin") == {"10435"}


def test_german_replies_are_understood():
    assert classify_reply("Re: Vorschau", "Nein danke, kein Interesse.") == "negative"
    assert classify_reply("Re: Vorschau", "Bitte löschen Sie meine Daten.") == "negative"
    assert classify_reply("Re: Vorschau", "Ja, gerne! Schicken Sie mir die Vorschau.") == "positive"
    assert classify_reply("Abwesenheitsnotiz: bis 20.10. nicht im Büro", "Ich bin im Urlaub.") == "auto"


# ------------------------------------------------------------------ Germany: letters first, e-mail only after consent
def test_germany_sends_letters_and_emails_only_businesses_that_asked(tmp_path):
    leads = [
        row(1, "Café Luise", email="hallo@cafe-luise.de", person="Maria Müller-Schmidt (inhaberin)",
            address="Kastanienallee 12, Berlin, 10435", legal="GmbH/UG/AG", priority="High"),
        row(2, "Bäckerei Kranz", email="info@baeckerei-kranz.de", address="Oderberger Str. 5, Berlin, 10435",
            signals="Objects to advertising (website notice)", priority="High"),
        row(3, "Bar Neun", email="kontakt@barneun.de", address="Torstraße 9, Berlin, 10119", status="Opted in"),
        row(4, "Imbiss ohne Adresse", email="post@imbiss-ohne.de"),
    ]
    sess, client = sheet_with(leads)
    smtp, clock = SmtpWorld(), Clock(wednesday_11("DE"))
    store = OutreachStore(str(tmp_path / "o.sqlite"))
    code, s = runner(country_cfg("DE"), store, client, clock, smtp).run()
    assert code == 0, s
    assert [m["To"] for m in smtp.sent] == ["kontakt@barneun.de"]        # only the business that asked
    body = smtp.sent[0].get_content()
    assert body.startswith("Guten Tag,") and "vielen Dank für Ihr Interesse" in body and SENDER["postal_address"] in body
    letters = tab(sess, "Letters")
    assert [x["Business"] for x in letters] == ["Café Luise"]           # not the objector, not the one without address
    x = letters[0]
    assert (x["Street"], x["Postcode"], x["City"], x["To (person)"]) == ("Kastanienallee 12", "10435", "Berlin",
                                                                         "Maria Müller-Schmidt")
    assert x["Letter"].startswith("Mehr Google-Bewertungen für Café Luise") and "Guten Tag Maria Müller-Schmidt," in x["Letter"]
    assert SENDER["postal_address"] in x["Letter"] and "Rabatte" in x["Letter"]
    assert status_of(sess, "key1") == "Letter queued" and status_of(sess, "key2") == "New"
    assert tab(sess, "WhatsApp Queue") == []                             # no cold WhatsApp in Germany
    # The owner sends the letters; one business answers "not interested": it is never contacted again.
    set_result(sess, "Letters", "key1", "Not interested")
    clock.t += 86400
    code, s = runner(country_cfg("DE"), store, client, clock, smtp).run()
    assert status_of(sess, "key1") == "Not interested (opted out)"
    assert any("not e-mailed (Germany" in n for n in s["notes"]) and len(smtp.sent) == 1
    assert "hallo@cafe-luise.de" in [r["Email or Phone"] for r in tab(sess, "Do Not Contact")]
    assert [x["Business"] for x in tab(sess, "Letters")] == ["Café Luise"]   # no second letter, no new one for key2/key4


# ------------------------------------------------------------------ UK: companies by e-mail, sole traders by letter
def test_uk_emails_limited_companies_and_writes_to_sole_traders(tmp_path):
    leads = [row(1, "Pasta House", email="hello@pastahouse.co.uk", legal="Ltd/LLP/PLC", address="1 Deansgate, Manchester, M3 1AZ"),
             row(2, "Joe's Cafe", email="joescafe@gmail.com", address="12 High Street, Manchester, M1 1AA")]
    sess, client = sheet_with(leads)
    smtp, clock = SmtpWorld(), Clock(wednesday_11("GB"))
    code, s = runner(country_cfg("GB"), OutreachStore(str(tmp_path / "o.sqlite")), client, clock, smtp).run()
    assert code == 0, s
    assert [m["To"] for m in smtp.sent] == ["hello@pastahouse.co.uk"]
    assert "We found this address on your website or public listing" in smtp.sent[0].get_content()   # Art. 14 notice
    letters = tab(sess, "Letters")
    assert [(x["Business"], x["Street"], x["Postcode"], x["City"]) for x in letters] == [
        ("Joe's Cafe", "12 High Street", "M1 1AA", "Manchester")]
    assert letters[0]["Letter"].startswith("Dear Joe's Cafe team,")


# ------------------------------------------------------------------ Australia: published addresses, no objectors
def test_australia_emails_only_published_addresses_without_a_no_marketing_notice(tmp_path):
    leads = [row(1, "Lygon Gelato", email="ciao@lygongelato.com.au", priority="High"),
             row(2, "Fitzroy Fitness", email="info@fitzroyfitness.com.au", signals="Objects to advertising (website notice)",
                 priority="High"),
             row(3, "Brunswick Barber", unverified="email: info@brunswickbarber.com.au (role address (guessed; domain accepts mail))",
                 priority="High")]
    sess, client = sheet_with(leads)
    smtp, clock = SmtpWorld(), Clock(wednesday_11("AU"))
    code, s = runner(country_cfg("AU", include_unverified=True), OutreachStore(str(tmp_path / "o.sqlite")), client, clock,
                     smtp).run()
    assert code == 0, s
    assert [m["To"] for m in smtp.sent] == ["ciao@lygongelato.com.au"]
    assert "letters" not in [t.lower() for t in sess.tabs] or tab(sess, "Letters") == []


# ------------------------------------------------------------------ USA: CAN-SPAM needs the sender's postal address
def test_us_live_sending_needs_a_postal_address(tmp_path):
    leads = [row(1, "Taco Joint", email="hola@tacojoint.com")]
    sess, client = sheet_with(leads)
    smtp, clock = SmtpWorld(), Clock(wednesday_11("US"))
    no_address = {**SENDER, "postal_address": ""}
    code, s = runner(country_cfg("US", sender=no_address), OutreachStore(str(tmp_path / "a.sqlite")), client, clock, smtp).run()
    assert code == 1 and smtp.sent == [] and any("postal_address" in n for n in s["notes"])
    code, s = runner(country_cfg("US"), OutreachStore(str(tmp_path / "b.sqlite")), client, clock, smtp).run()
    assert code == 0, s
    assert [m["To"] for m in smtp.sent] == ["hola@tacojoint.com"] and SENDER["postal_address"] in smtp.sent[0].get_content()
    assert 'reply "no"' in smtp.sent[0].get_content()


# ------------------------------------------------------------------ addresses, rules, shipped configs
def test_addresses_are_split_for_letters():
    country.use_country("DE", "Berlin")
    assert split_address("Kastanienallee 12, Berlin, 10435") == ("Kastanienallee 12", "10435", "Berlin")
    assert split_address("12, Kastanienallee, Prenzlauer Berg, Berlin, 10435") == ("Kastanienallee 12", "10435", "Berlin")
    assert split_address("Kastanienallee 12", "Berlin") == ("Kastanienallee 12", "", "Berlin")
    country.use_country("GB", "Manchester")
    assert split_address("12 High Street, Manchester, M1 1AA") == ("12 High Street", "M1 1AA", "Manchester")


def test_contact_rule_column_says_what_is_allowed():
    country.use_country("DE", "Berlin")
    assert country.contact_rule().startswith("Letter only")
    assert country.contact_rule(objects_to_advertising=True).startswith("Do not contact")
    country.use_country("GB", "Manchester")
    assert country.contact_rule("company").startswith("E-mail OK (limited company)")
    assert country.contact_rule("sole_trader").startswith("No cold e-mail")
    country.use_country("US", "Austin")
    assert "postal address" in country.contact_rule()


def test_shipped_campaign_files_load():
    first_six = {"config/germany-berlin.toml": "DE", "config/examples/usa-austin.toml": "US",
                 "config/examples/uk-manchester.toml": "GB", "config/examples/australia-melbourne.toml": "AU"}
    every_type = {"config/examples/canada-toronto.toml": "CA", "config/examples/ireland-dublin.toml": "IE",
                  "config/examples/newzealand-auckland.toml": "NZ", "config/examples/uae-dubai.toml": "AE",
                  "config/examples/singapore.toml": "SG"}
    assert sorted({**first_six, **every_type}) == sorted(glob.glob("config/germany-*.toml") + glob.glob("config/examples/*.toml"))
    for path, code in {**first_six, **every_type}.items():
        cfg = load_config(path)
        assert cfg["campaign"]["country"] == code and country.active().code == code
        keys = {c["key"] for c in cfg.categories}
        if path in first_six:
            assert keys == {"restaurant", "cafe", "bar", "bakery", "salon", "gym"}
        else:
            assert len(keys) == 15 and cfg["sheets"]["require_any"] == ["email", "whatsapp"]
        assert cfg["compliance"]["mode"] == "open-data"
    de = load_config("config/germany-berlin.toml")
    assert next(c for c in de.categories if c["key"] == "salon")["queries"][0] == "Friseur"   # German words override
    assert next(c for c in de.categories if c["key"] == "salon")["overture"]                  # shared codes kept
