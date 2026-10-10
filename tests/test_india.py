"""The India campaign: premium cafés, restaurants, bars, bakeries, salons and gyms in the big cities, their own tabs in
the Sheet, only businesses with their own website or Instagram, no budget eateries or chains. Synthetic data only."""
from __future__ import annotations

import glob
import itertools
from pathlib import Path

import tomllib
from conftest import make_config

from leadgen import country, market
from leadgen.config import load_config
from leadgen.db import DB
from leadgen.geo import haversine_km
from leadgen.quality import has_name_word, is_chain
from leadgen.report import sheet_condition

ROOT = Path(__file__).resolve().parent.parent


def city_files() -> list[str]:
    return [f for f in sorted(glob.glob(str(ROOT / "config" / "in" / "*.toml")))
            if not Path(f).name.startswith("_") and Path(f).stem not in ("fleet", "outreach")]


def test_india_is_the_default_market_and_us_stays_one_setting_away(monkeypatch):
    monkeypatch.delenv("MARKET", raising=False)
    assert market.current().code == "in" and market.current({"MARKET": "us"}).code == "us"
    assert market.current({"MARKET": "US "}).code == "us" and market.current({"MARKET": "mars"}).code == "in"


def test_india_city_files_premium_six_categories_own_tabs_and_no_overlap():
    files = city_files()
    assert len(files) == 16
    cfgs = [load_config(f) for f in files]
    for cfg in cfgs:
        assert cfg["campaign"]["country"] == "IN" and country.active().code == "IN"
        assert cfg["campaign"]["timezone"] == "Asia/Kolkata"
        assert {c["key"] for c in cfg.categories} == {"restaurant", "cafe", "bar", "bakery", "salon", "gym"}
        sh = cfg["sheets"]
        assert (sh["leads_tab"], sh["plan_tab"], sh["report_tab"]) == ("India Leads", "", "India Daily Report")
        assert sh["require_presence"] == ["website", "instagram"]
        assert cfg["plan"]["order"] == "center_out"
    assert len({c["campaign"]["id"] for c in cfgs}) == len({c["campaign"]["lead_id_prefix"] for c in cfgs}) == 16
    for a, b in itertools.combinations(cfgs, 2):        # a business never belongs to two cities
        d = haversine_km(*a["area"]["center"], *b["area"]["center"])
        assert d >= a["area"]["radius_km"] + b["area"]["radius_km"], (a["campaign"]["id"], b["campaign"]["id"])
    fleet = tomllib.loads((ROOT / "config" / "in" / "fleet.toml").read_text(encoding="utf-8"))
    assert fleet["cities"][0] == "kolkata" and sorted(fleet["cities"]) == sorted(Path(f).stem for f in files)


def test_india_outreach_has_its_own_tabs_rupee_offer_and_waits_for_approval():
    cfg = load_config(str(ROOT / "config" / "in" / "outreach.toml"))
    o = cfg["outreach"]
    assert o["tabs"]["outreach"] == "India Outreach" and o["tabs"]["whatsapp"] == "India WhatsApp Queue"
    assert o["tabs"]["dnc"] == "Do Not Contact"                      # shared with the US: a "no" counts everywhere
    assert "₹3,000" in o["offer"] and "$" not in o["offer"]
    assert o["email"]["enabled"] is False                            # paused until the India e-mail is approved
    assert o["email"]["days"] == ["mon", "tue", "wed", "thu", "fri", "sat"]
    assert o["whatsapp"]["include_mobiles"] is True and o["whatsapp"]["start_per_day"] <= 10
    assert "{sender_postal_address}" not in o["email"]["footer"]


def test_budget_places_and_chains_are_left_out_but_similar_names_are_kept():
    cfg = load_config(str(ROOT / "config" / "in" / "kolkata.toml"))
    words, chains = cfg["filters"]["exclude_name_words"], cfg["filters"]["exclude_chains"]
    for name, word in [("Sharma Mess", "mess"), ("Kolkata Momos", "momo"), ("Mukherjee Tea Stall", "tea stall"),
                       ("Glamour Beauty Parlour", "beauty parlour"), ("Punjabi Dhaba", "dhaba"),
                       ("Royal Wine Shop", "wine shop")]:
        assert has_name_word(name, words) == word, name
    for name in ("Messy Kitchen", "Olive Bar & Kitchen", "The Salon Studio", "Momoyama Japanese", "Paanch Tara Bistro"):
        assert has_name_word(name, words) is None, name
    assert is_chain("Starbucks Coffee - Park Street", chains) == "starbucks"
    assert is_chain("Domino's Pizza", chains) == "domino"
    assert is_chain("Cafe Coffee Day", chains) == "cafe coffee day"
    assert is_chain("The Barista Lounge", chains) is None              # an independent café with a common word


def test_only_businesses_with_their_own_website_or_instagram_go_to_the_sheet(tmp_path):
    cfg = make_config(sheets={"require_any": ["email", "whatsapp", "phone"], "require_presence": ["website", "instagram"]})
    db = DB(str(tmp_path / "kolkata.sqlite"))
    places = {"own-site": "https://www.olivebarandkitchen.in/", "zomato-only": "https://www.zomato.com/kolkata/x",
              "insta": None, "nothing": None, "linktree": "https://linktr.ee/somecafe", "site-no-contact": "https://a.in/"}
    for key, site in places.items():
        db.insert_place({"key": key, "name": key, "provider": "overture", "website": site, "found_date": "2026-10-10",
                         "qualified": 1})
        if key != "site-no-contact":
            db.add_contact(key, "phone", "+919830012345", source="website", confidence="high")
    db.add_contact("insta", "instagram", "https://www.instagram.com/insta_cafe/", source="website", confidence="high")
    db.conn.commit()
    keys = {r["key"] for r in db.q(f"SELECT key FROM places WHERE {sheet_condition(cfg)}")}
    assert keys == {"own-site", "insta"}
    plain = make_config(sheets={"require_any": ["email", "whatsapp", "phone"]})     # the US: any reachable business
    assert {r["key"] for r in db.q(f"SELECT key FROM places WHERE {sheet_condition(plain)}")} == set(places) - {"site-no-contact"}
