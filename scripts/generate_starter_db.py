#!/usr/bin/env python3
"""Generate starter.duckdb for the dbt escape room.

Run with:
    uv run --group scripts python scripts/generate_starter_db.py

Tables created
--------------
raw_customers          : 15,000 rows; 42 NL customers but country values
                         are dirty (mix of 'NL', 'nl', ' NL ', 'NL ') so
                         the answer only resolves after staging transforms.
raw_suppliers          : 25 rows; products reference these.
raw_product_categories : 20 rows; 5 root categories + 15 subcategories
                         (hierarchical via parent_category_id).
raw_products           : 300 SKUs; jaffle-shop themed.
raw_products_v2        : 300 SKUs with 12 price changes and 3 deactivations;
                         used as the "later state" for the Room 13 snapshot.
raw_orders             : ~48K rows; header level. `amount` is derived from
                         the sum of its order_items so the two granularities
                         reconcile. Includes 3 orphan rows + 1 dirty status.
raw_order_items        : ~120K rows; line items with product_id, quantity,
                         unit_price, discount_pct, line_total.
raw_payments           : ~57K rows; ~15% of orders have a zero-amount coupon.
raw_payments_late      : raw_payments + 3 late-arriving high-id rows.
raw_web_events         : ~250K rows; funnel events through 2025-12-31.
                         `event_at` is a TIMESTAMP suitable for freshness +
                         incremental watermarking.
raw_web_events_latest  : raw_web_events + ~2K new events through 2026-01-15,
                         with EXACTLY 42 events on 2026-01-15.
raw_reviews            : ~12K rows; product reviews (rating 1-5 + text).
                         Includes exactly 1 quality-violating row: a 5-star
                         review whose text contains the word 'terrible'.

All output is fully deterministic: fix SEED to regenerate identically.
After regenerating, update docs/PLAYTHROUGH.md with new puzzle answers.
"""

import csv
import random
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
from faker import Faker

# ── Configuration ────────────────────────────────────────────────────────────
SEED = 42
N_CUSTOMERS = 15_000
NL_COUNT = 42  # Room 1 answer: total NL customers after country normalization.

# Dirty-country breakdown — sums to NL_COUNT.
# Querying `raw` with `country = 'NL'` returns only the first bucket.
# Only after UPPER + TRIM do all four buckets resolve to 'NL'.
NL_BUCKETS = {
    "NL": 25,
    "nl": 8,
    " NL ": 5,
    "NL ": 4,
}
assert sum(NL_BUCKETS.values()) == NL_COUNT

N_PRODUCTS = 300
N_SUPPLIERS = 25
N_REVIEWS = 12_000
N_WEB_EVENTS = 248_000  # base table, before late-arriving rows

OUTPUT = Path(__file__).parent.parent / "starter.duckdb"

# ── Deliberate mistakes (Rooms 5 / 6 / 8 / 13 / 14) ──────────────────────────
# Room 5/6: 3 orphan orders reference customer_ids that don't exist
ORPHAN_CUSTOMER_IDS = [99901, 99902, 99903]

# Room 5/6: 1 order has a trailing-space dirty status value
WHITESPACE_ORDER_INDEX = 999  # 0-based index in the order list before orphans appended

# Room 13: products_v2 changes (id, new_base_price_cents, new_is_active)
# Product 42 carries the max-percent-increase answer (50.0%).
PRODUCT_PRICE_CHANGES = [
    (42, None, "PRICE_MULT_1_50"),    # +50.0% — Room 13 max-% answer
    (17, None, "PRICE_MULT_1_30"),    # +30.0%
    (88, None, "PRICE_MULT_1_25"),    # +25.0%
    (101, None, "PRICE_MULT_1_20"),   # +20.0%
    (134, None, "PRICE_MULT_1_15"),   # +15.0%
    (152, None, "PRICE_MULT_1_15"),   # +15.0%
    (199, None, "PRICE_MULT_1_10"),   # +10.0%
    (215, None, "PRICE_MULT_1_10"),   # +10.0%
    (227, None, "PRICE_MULT_1_08"),   # +8.0%
    (244, None, "PRICE_MULT_1_05"),   # +5.0%
    (271, None, "PRICE_MULT_1_05"),   # +5.0%
    (290, None, "PRICE_MULT_1_03"),   # +3.0%
]
PRODUCT_DEACTIVATIONS = [55, 178, 263]  # is_active → False in v2

# Room 14: late-arriving payments — kept for backwards-compatible exercises
LATE_PAYMENT_OFFSETS = [
    (1_000, 1_000, "gift_card", 9_500),     # $95.00
    (2_000, 2_000, "credit_card", 18_000),  # $180.00
    (9_999, 500, "bank_transfer", 4_242),   # $42.42
]

# Room 14 (primary): web_events latest — 42 events exactly on 2026-01-15.
WEB_EVENTS_LATEST_FINAL_DAY = date(2026, 1, 15)
WEB_EVENTS_LATEST_FINAL_DAY_COUNT = 42  # Room 14 answer
WEB_EVENTS_LATEST_EXTRA_DAYS = 14  # 2026-01-01 .. 2026-01-14 also get events
WEB_EVENTS_LATEST_PER_EXTRA_DAY_RANGE = (50, 200)  # random per-day count

# Room 2 (freshness): freshest event_at baked in. By the time anyone runs
# `dbt source freshness`, this date is months stale → WARN/ERROR.
# (Players don't need to know the exact value — they read it from output.)

# Room 8: review-quality violation — exactly 1 row, 5-star with 'terrible' text.
REVIEW_QUALITY_VIOLATION_INDEX = 4242

# ── Lookups ───────────────────────────────────────────────────────────────────
OTHER_COUNTRIES = ["BE", "DE", "FR", "ES", "IT", "US", "GB", "AU", "CA", "PL"]
COUNTRY_WEIGHTS = [18, 16, 14, 10, 8, 14, 7, 5, 5, 3]

STATUSES = ["completed", "pending", "cancelled"]
STATUS_WEIGHTS = [70, 20, 10]

PAYMENT_METHODS = ["credit_card", "bank_transfer", "gift_card"]
PAYMENT_WEIGHTS = [60, 25, 15]

DATE_START = date(2020, 1, 1)
DATE_END = date(2025, 12, 31)

# Jaffle-shop themed product taxonomy.
# Roots (id 1-5), then subcategories (id 6-20).
CATEGORIES = [
    # (id, name, parent_id)
    (1, "Sandwich", None),
    (2, "Bowl", None),
    (3, "Drink", None),
    (4, "Side", None),
    (5, "Dessert", None),
    (6, "Classic Jaffle", 1),
    (7, "Premium Jaffle", 1),
    (8, "Vegan Jaffle", 1),
    (9, "Rice Bowl", 2),
    (10, "Salad Bowl", 2),
    (11, "Grain Bowl", 2),
    (12, "Coffee", 3),
    (13, "Tea", 3),
    (14, "Cold Drink", 3),
    (15, "Hot Side", 4),
    (16, "Cold Side", 4),
    (17, "Snack", 4),
    (18, "Cake", 5),
    (19, "Pastry", 5),
    (20, "Cookie", 5),
]
LEAF_CATEGORY_IDS = [c[0] for c in CATEGORIES if c[2] is not None]

PRODUCT_NAME_TEMPLATES = {
    6: ["{} Jaffle", "Classic {} Toastie", "Cheesy {} Melt"],
    7: ["Truffle {} Jaffle", "{} Reserve Toastie", "Smoked {} Premium"],
    8: ["{} Vegan Jaffle", "Plant-based {} Toastie", "{} Vegan Melt"],
    9: ["{} Rice Bowl", "Spicy {} Donburi", "{} Hawaiian Bowl"],
    10: ["{} Garden Salad", "{} Caesar Bowl", "Crunchy {} Salad"],
    11: ["{} Grain Bowl", "Ancient Grain {} Mix", "{} Quinoa Bowl"],
    12: ["{} Latte", "{} Espresso", "Cold Brew {}"],
    13: ["{} Tea", "Iced {} Tea", "{} Chai"],
    14: ["{} Lemonade", "Sparkling {} Water", "{} Smoothie"],
    15: ["Hot {} Fries", "Loaded {} Wedges", "Crispy {} Bites"],
    16: ["Chilled {} Slaw", "Cold {} Salad", "Pickled {}"],
    17: ["{} Crisps", "{} Trail Mix", "{} Pretzels"],
    18: ["{} Layer Cake", "Mini {} Cake", "{} Cheesecake"],
    19: ["{} Croissant", "{} Danish", "{} Tart"],
    20: ["{} Cookie", "Chunky {} Biscuit", "{} Macaron"],
}
PRODUCT_NAME_FILLERS = [
    "BLT", "Tomato", "Spinach", "Mushroom", "Avocado", "Smoked Salmon",
    "Cheddar", "Brie", "Halloumi", "Pesto", "Caprese", "Italian", "Greek",
    "Mediterranean", "Bombay", "Tex-Mex", "Korean", "Vietnamese", "Hawaiian",
    "Detroit", "Chicago", "Bristol", "Brooklyn", "Tokyo", "Berlin",
]

# Base price range per ROOT category (in cents)
PRICE_RANGE_BY_ROOT = {
    1: (700, 1400),   # Sandwich
    2: (900, 1600),   # Bowl
    3: (250, 700),    # Drink
    4: (300, 600),    # Side
    5: (350, 800),    # Dessert
}

# Web events
EVENT_TYPES = ["page_view", "add_to_cart", "checkout_start", "purchase"]
UTM_SOURCES = ["google", "facebook", "instagram", "tiktok", "newsletter", "direct", "organic", None]
UTM_SOURCE_WEIGHTS = [25, 15, 12, 8, 10, 15, 10, 5]
UTM_MEDIUMS = ["cpc", "social", "email", "referral", "organic", None]
UTM_MEDIUM_WEIGHTS = [30, 20, 12, 10, 23, 5]
UTM_CAMPAIGNS = ["summer_2024", "holiday_2024", "spring_2025", "anniversary", "lunch_deal", None]
UTM_CAMPAIGN_WEIGHTS = [15, 18, 12, 10, 20, 25]

# Reviews
REVIEW_TEMPLATES_POS = [
    "Absolutely loved this. Will order again.",
    "Best lunch in town, no contest.",
    "Came with my team, everyone was happy.",
    "Solid flavour, great portion size.",
    "Reliable as always — never disappoints.",
    "Fresh ingredients and prompt service.",
    "Five stars all around.",
]
REVIEW_TEMPLATES_NEU = [
    "Decent but nothing special.",
    "Good on most days, off-days exist.",
    "Fine for a quick bite.",
    "Standard fare, fairly priced.",
    "Average — would order again only if nearby.",
]
REVIEW_TEMPLATES_NEG = [
    "Disappointing portion for the price.",
    "Cold by the time it arrived.",
    "Skipped my dietary request.",
    "Not what I expected from the photos.",
    "Slow service, mediocre food.",
]


# ── Helpers ───────────────────────────────────────────────────────────────────
def rand_date(start: date = DATE_START, end: date = DATE_END) -> date:
    return start + timedelta(days=random.randint(0, (end - start).days))


def rand_datetime(start: date = DATE_START, end: date = DATE_END) -> datetime:
    d = rand_date(start, end)
    return datetime.combine(d, datetime.min.time()) + timedelta(
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )


def rand_amount_cents() -> int:
    return random.randint(500, 50_000)


def round_to_5_cents(cents: int) -> int:
    """Round to nearest 5 cents so prices look human."""
    return int(round(cents / 5)) * 5


# ── Generators ────────────────────────────────────────────────────────────────
def build_customers(fake: Faker) -> list[dict]:
    rows: list[dict] = []

    # Generate NL customers across the dirty-country buckets so the total
    # cleans to NL_COUNT only after UPPER+TRIM normalization.
    for dirty_value, count in NL_BUCKETS.items():
        for _ in range(count):
            rows.append(
                {
                    "first_name": fake.first_name(),
                    "last_name": fake.last_name(),
                    "email": fake.unique.email(),
                    "country": dirty_value,
                    "created_at": rand_date(),
                }
            )

    # Remaining customers, non-NL (kept clean — only NL is dirty).
    for _ in range(N_CUSTOMERS - NL_COUNT):
        rows.append(
            {
                "first_name": fake.first_name(),
                "last_name": fake.last_name(),
                "email": fake.unique.email(),
                "country": random.choices(OTHER_COUNTRIES, weights=COUNTRY_WEIGHTS)[0],
                "created_at": rand_date(),
            }
        )

    # Shuffle so NL customers (and their dirty variants) aren't clustered,
    # then assign sequential IDs.
    random.shuffle(rows)
    for idx, row in enumerate(rows, start=1):
        row["id"] = idx

    return rows


def build_suppliers(fake: Faker) -> list[dict]:
    rows: list[dict] = []
    for i in range(1, N_SUPPLIERS + 1):
        rows.append(
            {
                "id": i,
                "name": fake.unique.company(),
                "country": random.choices(OTHER_COUNTRIES, weights=COUNTRY_WEIGHTS)[0],
                "contract_start_date": rand_date(end=date(2024, 12, 31)),
            }
        )
    return rows


def build_product_categories() -> list[dict]:
    return [
        {"id": cid, "name": name, "parent_category_id": parent}
        for cid, name, parent in CATEGORIES
    ]


def build_products() -> list[dict]:
    rows: list[dict] = []
    for pid in range(1, N_PRODUCTS + 1):
        leaf_id = LEAF_CATEGORY_IDS[(pid - 1) % len(LEAF_CATEGORY_IDS)]
        root_id = next(c[2] for c in CATEGORIES if c[0] == leaf_id)
        templates = PRODUCT_NAME_TEMPLATES[leaf_id]
        filler = random.choice(PRODUCT_NAME_FILLERS)
        name = random.choice(templates).format(filler)
        price_lo, price_hi = PRICE_RANGE_BY_ROOT[root_id]
        rows.append(
            {
                "id": pid,
                "sku": f"P{pid:04d}",
                "name": name,
                "category_id": leaf_id,
                "supplier_id": random.randint(1, N_SUPPLIERS),
                "base_price_cents": round_to_5_cents(random.randint(price_lo, price_hi)),
                "is_active": random.random() > 0.05,  # ~5% inactive in v1
                "launched_at": rand_date(end=date(2024, 6, 30)),
            }
        )

    # Pin product 42 to exactly $10.00 so its +50% bump in v2 is exactly
    # 50.0% (not 49.5% after rounding). This is the Room 13 answer.
    rows[41]["base_price_cents"] = 1000

    # Ensure all three "v2 deactivations" start active in v1 — otherwise the
    # diff (active→inactive) misses one and the Room 13 follow-up answer
    # underspecifies. Indices are id-1.
    for pid in PRODUCT_DEACTIVATIONS:
        rows[pid - 1]["is_active"] = True

    return rows


def build_products_v2(products: list[dict]) -> list[dict]:
    by_id = {p["id"]: p.copy() for p in products}
    multipliers = {
        "PRICE_MULT_1_50": 1.50,
        "PRICE_MULT_1_30": 1.30,
        "PRICE_MULT_1_25": 1.25,
        "PRICE_MULT_1_20": 1.20,
        "PRICE_MULT_1_15": 1.15,
        "PRICE_MULT_1_10": 1.10,
        "PRICE_MULT_1_08": 1.08,
        "PRICE_MULT_1_05": 1.05,
        "PRICE_MULT_1_03": 1.03,
    }
    for pid, _, key in PRODUCT_PRICE_CHANGES:
        old = by_id[pid]["base_price_cents"]
        new = round_to_5_cents(int(old * multipliers[key]))
        # Guarantee the increase didn't get rounded back to old (rare).
        if new <= old:
            new = old + 5
        by_id[pid]["base_price_cents"] = new
    for pid in PRODUCT_DEACTIVATIONS:
        by_id[pid]["is_active"] = False
    return [by_id[i] for i in sorted(by_id)]


def build_orders(customers: list[dict]) -> list[dict]:
    rows: list[dict] = []
    order_id = 1

    for cust in customers:
        n = random.choices(
            [0, 1, 2, 3, 4, 5, 6, 7, 8],
            weights=[5, 10, 20, 25, 20, 10, 5, 3, 2],
        )[0]
        for _ in range(n):
            rows.append(
                {
                    "id": order_id,
                    "customer_id": cust["id"],
                    "amount": None,  # filled by build_order_items
                    "status": random.choices(STATUSES, weights=STATUS_WEIGHTS)[0],
                    "ordered_at": rand_date(),
                }
            )
            order_id += 1

    # Deliberate mistake 1: one order with trailing-space dirty status
    rows[WHITESPACE_ORDER_INDEX]["status"] = "pending "

    # Deliberate mistake 2: orphan orders referencing non-existent customer_ids.
    for orphan_cid in ORPHAN_CUSTOMER_IDS:
        rows.append(
            {
                "id": order_id,
                "customer_id": orphan_cid,
                "amount": None,
                "status": "completed",
                "ordered_at": rand_date(),
            }
        )
        order_id += 1

    return rows


def build_order_items(orders: list[dict], products: list[dict]) -> list[dict]:
    """Generate line items and back-fill orders[].amount as the sum."""
    items: list[dict] = []
    item_id = 1
    products_by_id = {p["id"]: p for p in products}
    product_ids = list(products_by_id.keys())

    for order in orders:
        n_items = random.choices([1, 2, 3, 4, 5], weights=[40, 30, 15, 10, 5])[0]
        order_total_cents = 0
        for _ in range(n_items):
            product_id = random.choice(product_ids)
            quantity = random.choices([1, 2, 3, 4, 5], weights=[50, 25, 15, 7, 3])[0]
            unit_price_cents = products_by_id[product_id]["base_price_cents"]
            discount_pct = random.choices([0, 5, 10, 15, 20], weights=[80, 8, 6, 4, 2])[0]
            line_total_cents = int(quantity * unit_price_cents * (100 - discount_pct) / 100)
            order_total_cents += line_total_cents
            items.append(
                {
                    "id": item_id,
                    "order_id": order["id"],
                    "product_id": product_id,
                    "quantity": quantity,
                    "unit_price": round(unit_price_cents / 100, 2),
                    "discount_pct": discount_pct,
                    "line_total": round(line_total_cents / 100, 2),
                }
            )
            item_id += 1
        order["amount"] = round(order_total_cents / 100, 2)

    return items


def build_payments(orders: list[dict]) -> list[dict]:
    rows: list[dict] = []
    payment_id = 1
    orphan_ids = set(ORPHAN_CUSTOMER_IDS)

    for order in orders:
        if order["customer_id"] in orphan_ids:
            continue  # orphan orders never get payments

        roll = random.random()
        if roll < 0.15:
            # Two payments: coupon (zero-amount) + one regular
            rows.append(
                {
                    "id": payment_id,
                    "order_id": order["id"],
                    "payment_method": "coupon",
                    "amount": 0,
                }
            )
            payment_id += 1
            rows.append(
                {
                    "id": payment_id,
                    "order_id": order["id"],
                    "payment_method": random.choices(PAYMENT_METHODS, weights=PAYMENT_WEIGHTS)[0],
                    "amount": rand_amount_cents(),
                }
            )
            payment_id += 1
        elif roll < 0.20:
            for _ in range(2):
                rows.append(
                    {
                        "id": payment_id,
                        "order_id": order["id"],
                        "payment_method": random.choices(PAYMENT_METHODS, weights=PAYMENT_WEIGHTS)[0],
                        "amount": rand_amount_cents(),
                    }
                )
                payment_id += 1
        else:
            rows.append(
                {
                    "id": payment_id,
                    "order_id": order["id"],
                    "payment_method": random.choices(PAYMENT_METHODS, weights=PAYMENT_WEIGHTS)[0],
                    "amount": rand_amount_cents(),
                }
            )
            payment_id += 1

    return rows


def build_payments_late(payments: list[dict], orders: list[dict]) -> list[dict]:
    max_id = max(p["id"] for p in payments)
    valid_order_ids = [
        o["id"] for o in orders if o["customer_id"] not in set(ORPHAN_CUSTOMER_IDS)
    ]
    late = list(payments)
    for id_offset, order_idx, method, amount in LATE_PAYMENT_OFFSETS:
        late.append(
            {
                "id": max_id + id_offset,
                "order_id": valid_order_ids[order_idx % len(valid_order_ids)],
                "payment_method": method,
                "amount": amount,
            }
        )
    return late


def build_web_events(customers: list[dict], products: list[dict]) -> list[dict]:
    """Synthesize a funnel: sessions → views → carts → checkouts → purchases.

    ~30% of sessions are anonymous (customer_id NULL). Drop-off ratios are
    realistic for retail (~60% cart, ~33% checkout, ~50% purchase).
    """
    rows: list[dict] = []
    product_ids = [p["id"] for p in products]
    customer_ids = [c["id"] for c in customers]
    event_id = 1
    session_id = 1
    rows_generated = 0

    while rows_generated < N_WEB_EVENTS:
        anonymous = random.random() < 0.30
        customer_id = None if anonymous else random.choice(customer_ids)
        session_start = rand_datetime()
        utm_source = random.choices(UTM_SOURCES, weights=UTM_SOURCE_WEIGHTS)[0]
        utm_medium = random.choices(UTM_MEDIUMS, weights=UTM_MEDIUM_WEIGHTS)[0]
        utm_campaign = random.choices(UTM_CAMPAIGNS, weights=UTM_CAMPAIGN_WEIGHTS)[0]
        session_events: list[dict] = []

        # Every session starts with 1-4 page_view events.
        for i in range(random.choices([1, 2, 3, 4], weights=[40, 30, 20, 10])[0]):
            session_events.append(
                {
                    "event_type": "page_view",
                    "product_id": random.choice(product_ids) if random.random() < 0.6 else None,
                    "minutes_offset": i * random.randint(1, 3),
                }
            )

        # ~60% add to cart
        if random.random() < 0.60:
            session_events.append(
                {
                    "event_type": "add_to_cart",
                    "product_id": random.choice(product_ids),
                    "minutes_offset": len(session_events) + random.randint(1, 5),
                }
            )
            # of cart-ers, ~33% checkout
            if random.random() < 0.33:
                session_events.append(
                    {
                        "event_type": "checkout_start",
                        "product_id": session_events[-1]["product_id"],
                        "minutes_offset": session_events[-1]["minutes_offset"] + random.randint(1, 8),
                    }
                )
                # of checkouts, ~50% purchase
                if random.random() < 0.50:
                    session_events.append(
                        {
                            "event_type": "purchase",
                            "product_id": session_events[-1]["product_id"],
                            "minutes_offset": session_events[-1]["minutes_offset"] + random.randint(1, 4),
                        }
                    )

        for ev in session_events:
            rows.append(
                {
                    "id": event_id,
                    "session_id": session_id,
                    "customer_id": customer_id,
                    "event_type": ev["event_type"],
                    "product_id": ev["product_id"],
                    "utm_source": utm_source,
                    "utm_medium": utm_medium,
                    "utm_campaign": utm_campaign,
                    "event_at": (session_start + timedelta(minutes=ev["minutes_offset"])).isoformat(sep=" "),
                }
            )
            event_id += 1
            rows_generated += 1
            if rows_generated >= N_WEB_EVENTS:
                break
        session_id += 1

    return rows


def build_web_events_latest(base_events: list[dict], customers: list[dict], products: list[dict]) -> list[dict]:
    """Original events + ~2K late-arriving rows ending with exactly 42 on 2026-01-15."""
    rows = list(base_events)
    next_id = max(e["id"] for e in base_events) + 1
    next_session = max(e["session_id"] for e in base_events) + 1
    product_ids = [p["id"] for p in products]
    customer_ids = [c["id"] for c in customers]

    # Days 2026-01-01 .. 2026-01-14: random per-day count.
    for day_offset in range(WEB_EVENTS_LATEST_EXTRA_DAYS):
        day = date(2026, 1, 1) + timedelta(days=day_offset)
        per_day = random.randint(*WEB_EVENTS_LATEST_PER_EXTRA_DAY_RANGE)
        for _ in range(per_day):
            anonymous = random.random() < 0.30
            ts = datetime.combine(day, datetime.min.time()) + timedelta(
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
                seconds=random.randint(0, 59),
            )
            rows.append(
                {
                    "id": next_id,
                    "session_id": next_session,
                    "customer_id": None if anonymous else random.choice(customer_ids),
                    "event_type": random.choices(EVENT_TYPES, weights=[50, 30, 12, 8])[0],
                    "product_id": random.choice(product_ids) if random.random() < 0.7 else None,
                    "utm_source": random.choices(UTM_SOURCES, weights=UTM_SOURCE_WEIGHTS)[0],
                    "utm_medium": random.choices(UTM_MEDIUMS, weights=UTM_MEDIUM_WEIGHTS)[0],
                    "utm_campaign": random.choices(UTM_CAMPAIGNS, weights=UTM_CAMPAIGN_WEIGHTS)[0],
                    "event_at": ts.isoformat(sep=" "),
                }
            )
            next_id += 1
            next_session += 1

    # Day 2026-01-15: EXACTLY WEB_EVENTS_LATEST_FINAL_DAY_COUNT events.
    for i in range(WEB_EVENTS_LATEST_FINAL_DAY_COUNT):
        anonymous = random.random() < 0.30
        ts = datetime.combine(WEB_EVENTS_LATEST_FINAL_DAY, datetime.min.time()) + timedelta(
            minutes=i * 30 + random.randint(0, 15),
        )
        rows.append(
            {
                "id": next_id,
                "session_id": next_session,
                "customer_id": None if anonymous else random.choice(customer_ids),
                "event_type": random.choices(EVENT_TYPES, weights=[50, 30, 12, 8])[0],
                "product_id": random.choice(product_ids) if random.random() < 0.7 else None,
                "utm_source": random.choices(UTM_SOURCES, weights=UTM_SOURCE_WEIGHTS)[0],
                "utm_medium": random.choices(UTM_MEDIUMS, weights=UTM_MEDIUM_WEIGHTS)[0],
                "utm_campaign": random.choices(UTM_CAMPAIGNS, weights=UTM_CAMPAIGN_WEIGHTS)[0],
                "event_at": ts.isoformat(sep=" "),
            }
        )
        next_id += 1
        next_session += 1

    return rows


def build_reviews(customers: list[dict], products: list[dict]) -> list[dict]:
    rows: list[dict] = []
    product_ids = [p["id"] for p in products]
    customer_ids = [c["id"] for c in customers]

    for i in range(N_REVIEWS):
        rating = random.choices([1, 2, 3, 4, 5], weights=[5, 8, 17, 30, 40])[0]
        if rating >= 4:
            text = random.choice(REVIEW_TEMPLATES_POS)
        elif rating == 3:
            text = random.choice(REVIEW_TEMPLATES_NEU)
        else:
            text = random.choice(REVIEW_TEMPLATES_NEG)
        rows.append(
            {
                "id": i + 1,
                "product_id": random.choice(product_ids),
                "customer_id": random.choice(customer_ids),
                "rating": rating,
                "review_text": text,
                "reviewed_at": rand_date(),
            }
        )

    # Deliberate quality violation: 5-star review whose text contains 'terrible'.
    rows[REVIEW_QUALITY_VIOLATION_INDEX]["rating"] = 5
    rows[REVIEW_QUALITY_VIOLATION_INDEX]["review_text"] = (
        "Five stars for the price, but the wait was terrible."
    )

    return rows


# ── DuckDB writer ─────────────────────────────────────────────────────────────
def write_table(con: duckdb.DuckDBPyConnection, name: str, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"No rows for table {name}")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        tmp_path = f.name
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    try:
        con.execute(f"DROP TABLE IF EXISTS {name}")
        con.execute(
            f"CREATE TABLE {name} AS SELECT * FROM read_csv_auto('{tmp_path}', header=true, nullstr='')"
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    count = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    print(f"  {name:<30} {count:>8,} rows")


def main() -> None:
    print(f"Seeding RNG with SEED={SEED}")
    Faker.seed(SEED)
    random.seed(SEED)
    fake = Faker("en_US")

    print("\nGenerating data...")
    customers = build_customers(fake)
    suppliers = build_suppliers(fake)
    product_categories = build_product_categories()
    products = build_products()
    products_v2 = build_products_v2(products)
    orders = build_orders(customers)
    order_items = build_order_items(orders, products)  # back-fills order.amount
    payments = build_payments(orders)
    payments_late = build_payments_late(payments, orders)
    web_events = build_web_events(customers, products)
    web_events_latest = build_web_events_latest(web_events, customers, products)
    reviews = build_reviews(customers, products)

    print(f"\nWriting to {OUTPUT}")
    if OUTPUT.exists():
        OUTPUT.unlink()

    con = duckdb.connect(str(OUTPUT))
    print()
    write_table(con, "raw_customers", customers)
    write_table(con, "raw_suppliers", suppliers)
    write_table(con, "raw_product_categories", product_categories)
    write_table(con, "raw_products", products)
    write_table(con, "raw_products_v2", products_v2)
    write_table(con, "raw_orders", orders)
    write_table(con, "raw_order_items", order_items)
    write_table(con, "raw_payments", payments)
    write_table(con, "raw_payments_late", payments_late)
    write_table(con, "raw_web_events", web_events)
    write_table(con, "raw_web_events_latest", web_events_latest)
    write_table(con, "raw_reviews", reviews)
    con.close()

    # Sanity checks
    con = duckdb.connect(str(OUTPUT), read_only=True)
    nl_dirty_raw = con.execute("SELECT COUNT(*) FROM raw_customers WHERE country = 'NL'").fetchone()[0]
    nl_clean = con.execute(
        "SELECT COUNT(*) FROM raw_customers WHERE UPPER(TRIM(country)) = 'NL'"
    ).fetchone()[0]
    orphan_count = con.execute(
        "SELECT COUNT(*) FROM raw_orders WHERE customer_id NOT IN (SELECT id FROM raw_customers)"
    ).fetchone()[0]
    whitespace_count = con.execute(
        "SELECT COUNT(*) FROM raw_orders WHERE status != TRIM(status)"
    ).fetchone()[0]
    zero_payments = con.execute(
        "SELECT COUNT(*) FROM raw_payments WHERE amount = 0"
    ).fetchone()[0]
    late_max_id = con.execute("SELECT MAX(id) FROM raw_payments_late").fetchone()[0]
    late_amount = con.execute(
        f"SELECT ROUND(amount / 100.0, 2) FROM raw_payments_late WHERE id = {late_max_id}"
    ).fetchone()[0]
    events_2026_01_15 = con.execute(
        "SELECT COUNT(*) FROM raw_web_events_latest WHERE CAST(event_at AS DATE) = '2026-01-15'"
    ).fetchone()[0]
    max_event_at = con.execute("SELECT MAX(event_at) FROM raw_web_events").fetchone()[0]
    max_event_at_latest = con.execute("SELECT MAX(event_at) FROM raw_web_events_latest").fetchone()[0]
    max_price_increase_pct = con.execute(
        """
        SELECT ROUND(MAX((v2.base_price_cents - v1.base_price_cents) * 100.0 / v1.base_price_cents), 1)
        FROM raw_products v1
        JOIN raw_products_v2 v2 ON v1.id = v2.id
        WHERE v1.base_price_cents != v2.base_price_cents
        """
    ).fetchone()[0]
    deactivated_count = con.execute(
        """
        SELECT COUNT(*)
        FROM raw_products v1 JOIN raw_products_v2 v2 ON v1.id = v2.id
        WHERE v1.is_active AND NOT v2.is_active
        """
    ).fetchone()[0]
    bad_review_count = con.execute(
        "SELECT COUNT(*) FROM raw_reviews WHERE rating = 5 AND LOWER(review_text) LIKE '%terrible%'"
    ).fetchone()[0]
    n_products = con.execute("SELECT COUNT(*) FROM raw_products").fetchone()[0]
    order_items_reconcile = con.execute(
        """
        SELECT COUNT(*) FROM (
          SELECT o.id, o.amount, ROUND(SUM(oi.line_total), 2) AS items_sum
          FROM raw_orders o
          JOIN raw_order_items oi ON o.id = oi.order_id
          GROUP BY o.id, o.amount
          HAVING ABS(o.amount - ROUND(SUM(oi.line_total), 2)) > 0.05
        )
        """
    ).fetchone()[0]
    con.close()

    print("\nSanity checks:")
    print(f"  NL (raw, dirty) (Room 1 wrong-answer):  {nl_dirty_raw}  (expected {NL_BUCKETS['NL']})")
    print(f"  NL (after UPPER+TRIM) (Room 1 answer):  {nl_clean}  (expected {NL_COUNT})")
    print(f"  Orphan orders (Room 5):                 {orphan_count}  (expected {len(ORPHAN_CUSTOMER_IDS)})")
    print(f"  Whitespace status rows (Room 5):        {whitespace_count}  (expected 1)")
    print(f"  Zero-amount payments (Room 8 old):      {zero_payments}")
    print(f"  Late payment amount (legacy R14):       ${late_amount}  (expected $42.42)")
    print(f"  Events on 2026-01-15 (Room 14 answer):  {events_2026_01_15}  (expected {WEB_EVENTS_LATEST_FINAL_DAY_COUNT})")
    print(f"  Max event_at (raw_web_events):          {max_event_at}")
    print(f"  Max event_at (raw_web_events_latest):   {max_event_at_latest}")
    print(f"  Max price increase % (Room 13 answer):  {max_price_increase_pct}%  (expected 50.0)")
    print(f"  Deactivated products v1→v2 (R13):       {deactivated_count}  (expected 3)")
    print(f"  5-star + 'terrible' reviews (Room 8):   {bad_review_count}  (expected 1)")
    print(f"  Products: {n_products}  | Reconciliation mismatches: {order_items_reconcile}")

    size_mb = OUTPUT.stat().st_size / 1_048_576
    print(f"\nFile size: {size_mb:.2f} MB  (GitHub limit: 50 MB recommended, 100 MB hard)")
    print("\nDone! Update docs/PLAYTHROUGH.md with the new puzzle answers.")


if __name__ == "__main__":
    main()
