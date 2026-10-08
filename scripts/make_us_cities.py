"""Write one campaign file per US city into config/us/ (run again after editing CITIES).

    python scripts/make_us_cities.py

Each city: a circle (centre + radius) that does not overlap its neighbours, its time zone (for the plan's
calendar) and a short Lead ID prefix (AUS-17 is lead 17 of Austin). The shared settings are config/us/_base.toml;
which cities the fleet runs is config/us/fleet.toml.
"""
from __future__ import annotations

from pathlib import Path

E, C, M, P, H = "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "Pacific/Honolulu"
# slug, name, aliases, (lat, lng), radius km, time zone, Lead ID prefix
CITIES = [
    ("new-york", "New York", ["New York City", "NYC", "Manhattan", "Brooklyn", "Queens", "Bronx"], (40.7128, -74.0060), 25, E, "NYC"),
    ("los-angeles", "Los Angeles", ["LA", "Hollywood", "Santa Monica", "Pasadena", "Long Beach"], (34.0522, -118.2437), 35, P, "LAX"),
    ("chicago", "Chicago", ["Chicagoland", "Evanston"], (41.8781, -87.6298), 25, C, "CHI"),
    ("houston", "Houston", ["Houston TX", "HTX"], (29.7604, -95.3698), 35, C, "HOU"),
    ("phoenix", "Phoenix", ["Scottsdale", "Tempe", "Mesa", "Glendale", "Chandler"], (33.4484, -112.0740), 35, "America/Phoenix", "PHX"),
    ("philadelphia", "Philadelphia", ["Philly"], (39.9526, -75.1652), 20, E, "PHL"),
    ("san-antonio", "San Antonio", ["San Antonio TX", "SATX"], (29.4241, -98.4936), 25, C, "SAT"),
    ("san-diego", "San Diego", ["SD", "La Jolla", "Chula Vista"], (32.7157, -117.1611), 25, P, "SAN"),
    ("dallas", "Dallas", ["Dallas TX", "DFW", "Plano", "Irving", "Garland"], (32.7767, -96.7970), 25, C, "DAL"),
    ("fort-worth", "Fort Worth", ["Fort Worth TX", "Arlington"], (32.7555, -97.3308), 20, C, "FTW"),
    ("austin", "Austin", ["Austin TX", "ATX", "Round Rock"], (30.2672, -97.7431), 25, C, "AUS"),
    ("san-francisco", "San Francisco", ["SF", "Oakland", "Berkeley", "Bay Area"], (37.7749, -122.4194), 20, P, "SFO"),
    ("san-jose", "San Jose", ["Silicon Valley", "Santa Clara", "Sunnyvale"], (37.3382, -121.8863), 20, P, "SJC"),
    ("seattle", "Seattle", ["Bellevue", "Redmond"], (47.6062, -122.3321), 25, P, "SEA"),
    ("denver", "Denver", ["Aurora", "Lakewood"], (39.7392, -104.9903), 25, M, "DEN"),
    ("washington-dc", "Washington", ["Washington DC", "DC", "Arlington VA", "Alexandria", "Bethesda"], (38.9072, -77.0369), 20, E, "DCA"),
    ("boston", "Boston", ["Cambridge", "Somerville", "Quincy"], (42.3601, -71.0589), 20, E, "BOS"),
    ("nashville", "Nashville", ["Music City"], (36.1627, -86.7816), 20, C, "BNA"),
    ("las-vegas", "Las Vegas", ["Vegas", "Henderson", "Paradise"], (36.1699, -115.1398), 20, "America/Los_Angeles", "LAS"),
    ("miami", "Miami", ["Miami Beach", "Coral Gables", "Hialeah", "Fort Lauderdale"], (25.7617, -80.1918), 30, E, "MIA"),
    ("atlanta", "Atlanta", ["ATL", "Decatur", "Sandy Springs"], (33.7490, -84.3880), 30, E, "ATL"),
    ("orlando", "Orlando", ["Kissimmee", "Winter Park"], (28.5383, -81.3792), 25, E, "MCO"),
    ("tampa", "Tampa", ["St. Petersburg", "St Pete", "Clearwater"], (27.9506, -82.4572), 30, E, "TPA"),
    ("charlotte", "Charlotte", ["Charlotte NC"], (35.2271, -80.8431), 20, E, "CLT"),
    ("portland", "Portland", ["Portland OR", "PDX"], (45.5152, -122.6784), 20, P, "PDX"),
    ("minneapolis", "Minneapolis", ["Saint Paul", "St. Paul", "Twin Cities"], (44.9778, -93.2650), 20, C, "MSP"),
    ("new-orleans", "New Orleans", ["NOLA", "Metairie"], (29.9511, -90.0715), 15, C, "MSY"),
    ("salt-lake-city", "Salt Lake City", ["SLC"], (40.7608, -111.8910), 20, M, "SLC"),
    ("raleigh", "Raleigh", ["Durham", "Cary", "Research Triangle"], (35.7796, -78.6382), 25, E, "RDU"),
    ("honolulu", "Honolulu", ["Waikiki", "Oahu"], (21.3069, -157.8583), 15, H, "HNL"),
]

TEMPLATE = """# {name} - one city of the US fleet (config/us/fleet.toml). Shared settings: _base.toml.
# Made by scripts/make_us_cities.py - edit the list there and run it again.
include = ["../shared/categories.toml", "_base.toml"]

[campaign]
id = "us-{slug}"
timezone = "{tz}"
lead_id_prefix = "{prefix}"

[area]
name = "{name}"
aliases = [{aliases}]
center = [{lat}, {lng}]
radius_km = {radius}
"""


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "config" / "us"
    out.mkdir(parents=True, exist_ok=True)
    for slug, name, aliases, (lat, lng), radius, tz, prefix in CITIES:
        (out / f"{slug}.toml").write_text(TEMPLATE.format(
            name=name, slug=slug, tz=tz, prefix=prefix, aliases=", ".join(f'"{a}"' for a in aliases),
            lat=lat, lng=lng, radius=radius), encoding="utf-8")
    print(f"wrote {len(CITIES)} city files to {out}")


if __name__ == "__main__":
    main()
