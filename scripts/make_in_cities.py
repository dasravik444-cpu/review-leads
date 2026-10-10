"""Write one campaign file per Indian city into config/in/ (run again after editing CITIES).

    python scripts/make_in_cities.py

Each city: a circle around the city centre, large enough to take in its upmarket districts (listed as aliases)
and never overlapping another city's (a business belongs to one city only),
searched from the centre outwards, and a short Lead ID prefix (KOL-17 is lead 17 of Kolkata). Which businesses are
kept (the premium focus: own website or Instagram, no budget eateries, no big chains) is config/in/_base.toml; which
cities the robot works through, in which order, is config/in/fleet.toml.
"""
from __future__ import annotations

from pathlib import Path

# slug, name, aliases (other names and the districts people write in addresses), (lat, lng), radius km, prefix
CITIES = [
    ("kolkata", "Kolkata", ["Calcutta", "Salt Lake", "New Town", "Park Street", "Ballygunge", "Alipore"],
     (22.5726, 88.3639), 15, "KOL"),
    ("mumbai", "Mumbai", ["Bombay", "Bandra", "Juhu", "Worli", "Lower Parel", "Colaba", "Andheri", "Powai"],
     (19.0760, 72.8777), 22, "BOM"),
    ("delhi", "Delhi", ["New Delhi", "Connaught Place", "Hauz Khas", "Greater Kailash", "Vasant Kunj", "Saket"],
     (28.6139, 77.2090), 13, "DEL"),
    ("bengaluru", "Bengaluru", ["Bangalore", "Indiranagar", "Koramangala", "MG Road", "Whitefield", "HSR Layout"],
     (12.9716, 77.5946), 18, "BLR"),
    ("gurugram", "Gurugram", ["Gurgaon", "Cyber Hub", "Golf Course Road", "Sohna Road"], (28.4595, 77.0266), 11, "GGN"),
    ("hyderabad", "Hyderabad", ["Secunderabad", "Banjara Hills", "Jubilee Hills", "HITEC City", "Gachibowli"],
     (17.3850, 78.4867), 18, "HYD"),
    ("pune", "Pune", ["Koregaon Park", "Kalyani Nagar", "Baner", "Viman Nagar", "Aundh"], (18.5204, 73.8567), 15, "PNQ"),
    ("chennai", "Chennai", ["Madras", "T Nagar", "Nungambakkam", "Adyar", "Anna Nagar", "OMR"], (13.0827, 80.2707), 15, "MAA"),
    ("noida", "Noida", ["Gautam Buddh Nagar"], (28.5355, 77.3910), 6.5, "NOI"),   # Sector 18 is in Delhi's circle
    ("ahmedabad", "Ahmedabad", ["Amdavad", "SG Highway", "Prahlad Nagar", "Bodakdev"], (23.0225, 72.5714), 15, "AMD"),
    ("chandigarh", "Chandigarh", ["Mohali", "Panchkula", "Tricity"], (30.7333, 76.7794), 12, "IXC"),
    ("jaipur", "Jaipur", ["C Scheme", "Malviya Nagar", "Vaishali Nagar"], (26.9124, 75.7873), 12, "JAI"),
    ("goa", "Goa", ["Panaji", "Panjim", "Calangute", "Candolim", "Anjuna", "Assagao"], (15.4909, 73.8278), 20, "GOI"),
    ("kochi", "Kochi", ["Cochin", "Ernakulam", "Panampilly Nagar", "Kakkanad"], (9.9312, 76.2673), 12, "COK"),
    ("lucknow", "Lucknow", ["Hazratganj", "Gomti Nagar"], (26.8467, 80.9462), 12, "LKO"),
    ("indore", "Indore", ["Vijay Nagar", "Palasia"], (22.7196, 75.8577), 10, "IDR"),
]

TEMPLATE = """# {name} - one city of the India campaign (config/in/fleet.toml). Shared settings: _base.toml.
# Made by scripts/make_in_cities.py - edit the list there and run it again.
include = ["../shared/categories.toml", "_base.toml"]

[campaign]
id = "in-{slug}"
timezone = "Asia/Kolkata"
lead_id_prefix = "{prefix}"

[area]
name = "{name}"
aliases = [{aliases}]
center = [{lat}, {lng}]
radius_km = {radius}
"""


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "config" / "in"
    out.mkdir(parents=True, exist_ok=True)
    for slug, name, aliases, (lat, lng), radius, prefix in CITIES:
        (out / f"{slug}.toml").write_text(TEMPLATE.format(
            name=name, slug=slug, prefix=prefix, aliases=", ".join(f'"{a}"' for a in aliases),
            lat=lat, lng=lng, radius=radius), encoding="utf-8")
    print(f"wrote {len(CITIES)} city files to {out}")


if __name__ == "__main__":
    main()
