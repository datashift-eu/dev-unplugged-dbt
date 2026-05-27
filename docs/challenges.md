# dbt Escape Room — Challenge Book

Welcome aboard. Seven planets. Seventeen challenges. Build your way out.

Each challenge has two parts:

- **A small dbt task** — write a model, configure YAML, add a macro, fix a bug, run a command.
- **A business question** whose answer is only computable if your build is correct.

Type your answer at the Voyager prompt. Type `scan` for the next hint (each hint costs 10% of the challenge's points). Type `skip` to come back later. Type `status` to see where you are across all planets.

Difficulty scale: `easy` → `medium` → `hard` → `expert`. Points scale with difficulty. Total mission credits: 775.

---

## Planet 1 — Terra Stagia (Foundations)

> Three raw tables. One broken model. Welcome to the staging layer —
> the only place in this warehouse where the data is allowed to be
> honest about how messy it really is.

### Challenge 101 — First Light

`easy · 15 points`

A starter dbt project lands on your desk with one model in it, and that model is broken. It won't even parse.

First task: make it work. Then make it good.

"Good" is what staging models exist for: rename source columns to domain-friendly names, lock down types, and normalize messy values. Take a look at the raw customer table — particularly the country column. You'll notice the source system isn't consistent about how it writes the same country (which is exactly the kind of mess that staging exists to clean up).

**Business question:** how many of your customers are based in the Netherlands?

---

### Challenge 102 — Know Your Sources

`easy · 20 points`

Your staging model currently reads from a hardcoded raw table name. That's a brittle pattern: dbt can't see the lineage, nobody can monitor source freshness, and a rename in the source system means hunting every FROM clause in the project.

dbt has a first-class way to declare external (raw) tables and reference them — use it. Convert the existing model to that pattern, declare every raw business table your staging models touch, and add a second staging model — for orders, at `models/staging/stg_orders.sql` — exposing order_id, customer_id, amount, status, and the order date (cast properly).

Once everything's wired, this command lists the model resources downstream of your declared source (i.e. the blast radius if any raw business table changed):

    just dbt ls --quiet --select source:jaffle_shop+ --resource-type model

**Business question:** how many models does it list?

Docs: <https://docs.getdbt.com/docs/build/sources>

---

### Challenge 103 — The Seed Vault

`easy · 20 points`

Some reference data isn't raw source data — it's small, slow-changing, and owned by your team. A four-row mapping of payment methods to their display names and processing fees is a perfect example. It doesn't belong in `raw_X` (no source system produced it) and it doesn't belong inside a model (it's data, not logic).

dbt has a separate mechanism for team-owned reference data. **First**, get the finance team's mapping into the project — header row and four data rows, exactly as below:

    payment_method,payment_method_name,processing_fee_pct
    credit_card,Credit Card,2.9
    coupon,Coupon,0.0
    bank_transfer,Bank Transfer,0.5
    gift_card,Gift Card,0.0

After loading, take a quick look in your database — the mapping should now exist as a real table in `main`, just like a `raw_X` table would. You won't use it from a model yet (that join belongs in the intermediate layer, which is the next planet), but it's persisted and ready.

**Second**, build `stg_payments` at `models/staging/` — pure staging only, no joins, no enrichment. It should expose `payment_id`, `order_id`, `payment_method`, and the payment amount converted into dollars.

(You'll also notice the project ships with another seed file, `iso_country_codes.csv` — that's for a much later challenge. Leave it alone for now.)

**Business question:** how many dollars of revenue have come through bank transfers across all time?

Docs: <https://docs.getdbt.com/docs/build/seeds>

---

## Planet 2 — Refactoria (Building & Trust)

> The staging layer exists. Now you stack things on top of it: refs,
> joins across layers, schema tests, and the one command that runs them
> all in dependency order. Data without tests is just vibes.

### Challenge 201 — Chain Reaction

`medium · 30 points`

Staging models should stay 1:1 with source — no joins, no enrichment. That work belongs in an intermediate layer. The intermediate is where you start combining things: joining the team-owned mapping seed onto the staging payments, aggregating to a more useful grain.

Build `int_payments` at `models/intermediate/`. Grain: one row per unique `(order_id, payment_method_name)` — so an order paid partly by credit card and partly by coupon yields two rows. Each row should expose the `order_id`, the human-readable `payment_method_name` (from the seed — not the raw code), the total dollar amount paid by that method on that order, and the count of payment events that make up that total. The default materialization for intermediate models in this project is `view`.

**Business question:** how many orders in your warehouse were paid using more than one distinct payment method?

Docs: <https://docs.getdbt.com/reference/dbt-jinja-functions/ref>

---

### Challenge 202 — Trust, but Verify

`medium · 35 points`

Data without tests is just vibes. dbt has a built-in test framework for declarative, reusable assertions about your models — uniqueness, non-nullness, referential integrity, allowed value sets.

Add tests that capture the obvious invariants of your staging models: primary keys are unique and non-null, foreign keys actually reference something that exists, and status values come from a known short list (`completed`, `pending`, `cancelled`). When you run them, at least two will fail — and the failures point at real issues the staging layer should clean up. Don't fix them yet; just investigate.

**Business question:** how many orders in your project reference a customer that doesn't exist?

Docs: <https://docs.getdbt.com/docs/build/data-tests>

---

### Challenge 203 — The Full Build

`medium · 35 points`

The two failures from the previous challenge both belong to the orders staging model. That's not a coincidence — cleaning conformance issues so downstream consumers can trust the data is exactly what the staging layer is for.

Fix the orders staging model so that orphan orders disappear and the status values conform to the allowed set. Drop orphans via an INNER JOIN on `ref('stg_customers')` (i.e. join staging → staging, not staging → source). Earlier challenges emphasized "staging stays 1:1 with source, no joins" — referential-integrity conformance against another staging model is the canonical exception, and using `ref()` keeps the lineage visible to dbt.

Then run a single dbt command that rebuilds models in dependency order AND runs every test, and confirm everything passes.

**Business question:** after your cleanup, how many orders did your model drop compared to raw?

---

## Planet 3 — Selectoria (Surgical Control)

> Big projects don't run every model on every change. You need to wield
> the selector language with precision — graph operators, intersections,
> resource-type filters — and you need tests that catch what built-in
> tests can't.

### Challenge 301 — Selective Operations

`medium · 30 points`

In real projects, you don't run every model on every change — you run exactly the subset that matters. dbt's selector language is the tool: graph operators for upstream/downstream, intersection for "models that are both X and Y", resource-type filters, source selectors.

The question you'll answer is one analytics engineers ask whenever a model is about to change: who downstream depends on me? At four models you could trace it by hand, at four hundred you cannot — so build the muscle now.

**Business question:** using only `dbt ls` with selectors (no SQL, no opening project files), how many model resources depend on `stg_payments` — NOT counting `stg_payments` itself?

---

### Challenge 302 — Custom Tests

`hard · 55 points`

Built-in tests cover the obvious invariants. Real projects need custom ones. dbt supports two flavours: **generic** tests (reusable across models, parameterized by model + column) and **singular** tests (one-off assertions specific to a single piece of business logic).

Write one of each.

> **Generic:** an `is_positive` test that fails when a column's value is ≤ 0. Apply it to the total amount on your intermediate payments model. Heads up: this test WILL fail — your intermediate has legitimate zero-amount rows for coupon-paid orders. That's the pedagogical moment. In a real project you'd either tighten the test to `< 0` or treat zero as a quality violation; for the challenge, leave the failure visible.
>
> **Singular:** a quality check on the product reviews. A 5-star review whose text contains the word "terrible" (case-insensitive) is almost certainly miscategorized — surface those.

A dbt test passes when its SELECT returns zero rows. The puzzle below asks how many rows your singular test returns (i.e., how many violations it surfaces), NOT whether it passes.

**Business question:** how many "5-star terrible" reviews exist in the review data?

---

## Planet 4 — Documentum (Communicate & DRY)

> Code that nobody can read is code that nobody trusts. Two skills:
> describing what you built so the next analyst doesn't Slack you,
> and extracting repeated SQL into macros — without accidentally
> shadowing a package you didn't mean to.

### Challenge 401 — Documentation Station

`medium · 30 points`

If it isn't documented, it doesn't exist. dbt turns the descriptions you write in YAML into a navigable docs site with lineage diagrams, column-level metadata, and search.

Add a model-level description for every model you've built so far (stage models plus the intermediate). Pick the most ambiguous columns in each model — the ones a new analyst would Slack you about — and describe them too. Generate the docs site and browse the lineage view for your intermediate model. Confirm the graph reaches all the way back to raw.

**Business question:** how many of your models have a model-level description set?

Docs: <https://docs.getdbt.com/reference/resource-properties/description>

#### Bonus (optional)

`dbt-osmosis` propagates column descriptions from upstream to downstream automatically. Install with `uv add dbt-osmosis` and try it on your intermediate model — column descriptions you wrote on staging will cascade.

---

### Challenge 402 — The Macro Workshop

`hard · 60 points`

You've already written `amount / 100.0` once. If you write it again somewhere else, you've started repeating yourself — and the day someone changes the convention you'll be hunting every instance. Extract it into a macro.

Build two macros. The first wraps cents-to-dollars conversion: takes a column name and returns the SQL fragment `ROUND(CAST(<col> AS DECIMAL) / 100.0, 2)` (rounded to two decimal places — same precision as Challenge 103, so the downstream answers don't drift). Use it in `stg_payments` to replace the inline calculation.

The second is a surrogate-key generator that MD5-hashes a list of fields. Specifications you need to follow exactly so the hash is deterministic:

> - **Fields, in order:** `[order_id, payment_id]`
> - **Cast each field:** `CAST(<field> AS VARCHAR)` BEFORE the COALESCE. `order_id` is an INTEGER — COALESCE can't mix an integer with the `'_null_'` string sentinel, so the cast has to happen first or you'll hit a type-mismatch error.
> - **Separator:** the literal pipe character `'|'`
> - **NULL sentinel:** COALESCE NULL → the literal string `'_null_'` (so `(NULL,'x')` doesn't collide with `(NULL,NULL)`)
> - **Output:** MD5 of the joined string, lowercase hex

Give the macro the exact same name as the surrogate-key macro in `dbt_utils` (`generate_surrogate_key`). Add a `payment_key` column to `stg_payments` by calling it UNQUALIFIED — i.e. `{{ generate_surrogate_key(['order_id', 'payment_id']) }}` — and observe which implementation wins. (Two name-resolution rules to understand: unqualified macro calls resolve to your project's macros first; the separate `dispatch` config is what would force calls written as `dbt_utils.generate_surrogate_key(...)` through your override too. The puzzle only requires the unqualified path — try dispatch as a bonus.)

There's a SQL scoping gotcha: the column you hash on is a SELECT alias of a source column. Most engines can't reference a SELECT alias from another expression in the same SELECT — structure with a CTE so the rename is in scope before the macro call.

**Business question:** what are the first 8 characters of the `payment_key` for `payment_id = 1`?

Docs: <https://docs.getdbt.com/docs/build/jinja-macros>

#### Bonus — dispatch

Try `{{ dbt_utils.generate_surrogate_key(['order_id', 'payment_id']) }}` explicitly — different hash (different separator). To force *all* references to `dbt_utils.generate_surrogate_key` (including from other packages) to use your override too, configure `dispatch:` in `dbt_project.yml` with `search_order: ["dbt_escape_room", "dbt_utils"]`. Flip the order, re-run, observe the hash change. This is exactly how teams swap in a project-wide hash function (e.g., SHA256 for compliance).

---

## Planet 5 — Materia (Shaping Reality)

> Every model becomes a database object — until it doesn't. Choose the
> materialization wisely, and learn what dbt does NOT clean up when you
> change your mind. Then bend the schema namespace to your will.

### Challenge 501 — Materializations & Ghost Objects

`medium · 30 points`

Not every model should be a database table. Views save space but cost query time. Ephemeral models exist only as CTEs inlined into downstream queries. Tables cost storage but speed up reads. The right choice depends on the model's place in the pipeline.

Reconfigure the project so staging models stay as views, intermediate models become ephemeral, and marts (which you'll start building in a later planet) materialize as tables. Then rebuild and look closely at what objects actually exist in the database.

There's a gotcha here that catches every dbt newcomer once. Find it — and DO NOT clean it up yet; the puzzle answer depends on observing the world as dbt left it.

**Business question:** immediately after your reconfigure-and-rebuild (no manual cleanup), how many views exist in the main schema?

Docs: <https://docs.getdbt.com/docs/build/materializations>

---

### Challenge 502 — Schema Mastery

`hard · 50 points`

Beyond toy projects, models land in multiple schemas: marts in `marts`, snapshots in `snapshots`, raw mirrors in `raw`. dbt has a `+schema:` config for this. The default behaviour is famously surprising — every team in production ends up overriding it.

Set up the project so that any future marts models will land in a `marts` schema and snapshots will land in a `snapshots` schema. Note that marts configuration sits under `models:` in `dbt_project.yml`, but snapshot configuration sits under a separate top-level `snapshots:` block (and uses the key `+target_schema`, not `+schema`) — easy to miss. Then, before the override takes effect everywhere, investigate what dbt would have produced *by default* if no override existed.

To actually observe the default schema in action, the marts folder needs at least one model (otherwise there's nothing for the schema config to materialize). Create a tiny throwaway probe model under `models/marts/` (one row of anything) — you'll delete it after the challenge. There's a macro in this project that handles the override — temporarily disable it (rename to `.bak`), re-parse or rebuild your probe, observe the schema dbt actually uses, then restore the macro and delete the probe.

**Business question:** with the override disabled, what schema would dbt produce for a marts-configured model when the target schema is `main`? Format: lowercase, single underscore.

Docs: <https://docs.getdbt.com/docs/build/custom-schemas>

---

## Planet 6 — Tempus (Time Travel)

> Source systems lose history. dbt gives you two tools to keep your own:
> snapshots track row-level changes over time (SCD2), and incremental
> models let you process only what's new without rebuilding the world.

### Challenge 601 — Snapshot: Freeze Frame

`hard · 60 points`

Source systems lose history. The product catalog you have today overwrites prices when the merchandiser changes them — but the finance team needs to ask "what was SKU X priced at on date Y?". dbt's snapshot feature builds Slowly Changing Dimension Type 2 history for exactly this case.

The `raw_products` table represents the catalog today. There's also a `raw_products_v2` — a hypothetical "later state" with twelve price changes and three deactivations. Build a snapshot of the products catalog, run it against the current state to capture today's prices, then point it at the later state and run it again so the changes get captured as SCD2 rows. This source has no reliable `updated_at` column, so think about which snapshot strategy applies.

**Business question:** across all the price changes captured in the snapshot, what's the largest percentage increase? (1 decimal place.)

Docs: <https://docs.getdbt.com/docs/build/snapshots>

---

### Challenge 602 — Incremental: Don't Rebuild the World

`hard · 65 points`

The web events table keeps growing. Rebuilding it from scratch every time something downstream changes is wasteful — and at real scale, impossible. dbt's incremental materialization processes only what's new on subsequent runs.

Build an incremental staging model over the web events table. On the initial run it loads everything; on subsequent runs it loads only events newer than what's already in the table. There's a separate "latest" version of the source containing late-arriving rows from 2026-01-01 to 2026-01-15 — after your initial load, swap the model to read from that one and re-run. Only the new rows should land.

Use the event timestamp as your watermark, not the row id. IDs can be reused, sharded, or non-monotonic — timestamps are the safer choice.

**Business question:** how many events occurred on 2026-01-15?

Docs: <https://docs.getdbt.com/docs/build/incremental-models>

#### Bonus (optional)

Run with `--full-refresh` and observe dbt drop and rebuild from scratch. When is that actually the right call in production? (Hint: schema changes, late-arriving backfills, watermark drift.)

---

## Planet 7 — Marsius (Pay Off)

> Everything you've built so far stacks into one place: marts. Line-item
> facts, customer segments, marketing attribution. Three rooms, three
> dbt features per room — refs across many layers, tests that span
> models, and the incremental model from Tempus finally getting used.

### Challenge 701 — The Line-Item Fact

`hard · 60 points`

Order headers are fine for payment-related questions, but most analytical questions live at the *line* grain — revenue by product, by category, the impact of discounts. The mart layer is where you build the workhorse facts that BI tools will actually query.

Build a line-item fact that brings together order lines with their product and customer context. One row per line item. Denormalize the useful dimensions (product SKU, customer country, category name) onto the fact so analysts don't have to chase joins.

Prerequisite: you don't have staging models yet for order items, products, or product categories — build small `stg_` ones first (same patterns as Planet 1: rename, cast, no joins), declare their sources, then build the fact on top of them.

For revenue, use the pre-computed `line_total` column on each line item (already factors in quantity, unit_price, and discount).

Then add a referential-integrity test that catches any line referencing a product that doesn't exist. The test must pass.

**Business question:** which single product (by SKU) has generated the most revenue across all time?

---

### Challenge 702 — RFM Segments

`expert · 90 points`

RFM is a classic CRM segmentation: **R**ecency (days since last order), **F**requency (number of orders), **M**onetary (lifetime spend). You bucket each into quintiles, concatenate the scores, and classify customers into segments like "champions" (high on all three) and "lost" (low on all three).

Build an aggregate mart at customer grain. Source it from the line-item fact you built in 701 — that's where the analytical truth lives. For each customer, compute the three RFM dimensions, score each into 5 buckets via window functions, then apply the segmentation rules below in this exact order (first match wins):

    r >= 4 AND f >= 4 AND m >= 4   → champions
    r >= 4 AND f <= 2              → new_customers
    r >= 3 AND f >= 3              → loyal
    r <= 2 AND m >= 3              → at_risk
    r <= 2 AND f <= 2              → lost
    otherwise                      → other

Specifications you need to follow so the puzzle answer is deterministic:

> - **As-of date for recency:** `DATE '2026-01-01'` (hardcoded)
> - **Recency direction:** lower `recency_days` → higher `r_score`. `NTILE(5) OVER (ORDER BY recency_days DESC, customer_id)` — the `customer_id` tiebreaker prevents non-determinism on ties.
> - **Frequency:** `COUNT(DISTINCT order_id)` from the fact. `NTILE(5) OVER (ORDER BY frequency ASC, customer_id)`.
> - **Monetary:** `SUM(line_total)` from the fact (already discount-adjusted; ignores order status). `NTILE(5) OVER (ORDER BY monetary ASC, customer_id)`.

Add uniqueness and not-null tests on the customer key — both must pass.

**Business question:** how many customers fall into the `'champions'` segment?

---

### Challenge 703 — The Marketing Funnel

`expert · 90 points`

The marketing team's first question is always "which channel converts?". Without a canonical funnel mart, every analyst writes their own version and gets different numbers — and the team stops trusting the data.

Build a funnel mart at `utm_source` grain on top of the incremental web events model from the previous planet (this is the payoff — that incremental model finally gets consumed). Per channel, count distinct sessions (one row per `session_id`) at each of these stages:

> - **viewed** — a `page_view` event WHERE `product_id IS NOT NULL`
> - **added_to_cart** — an `add_to_cart` event
> - **checked_out** — a `checkout_start` event
> - **purchased** — a `purchase` event

Compute a cart-to-purchase conversion percentage rounded to 1 decimal place. Bucket NULL `utm_source` as `'(none)'`.

Add not-null tests on the channel name and session count.

**Business question:** which `utm_source` has the highest cart-to-purchase percentage? (Ignore `'(none)'`.)

---

## Mission summary

| ID  | Title                       | Planet         | Difficulty | Points |
|-----|-----------------------------|----------------|------------|--------|
| 101 | First Light                 | Terra Stagia   | easy       | 15     |
| 102 | Know Your Sources           | Terra Stagia   | easy       | 20     |
| 103 | The Seed Vault              | Terra Stagia   | easy       | 20     |
| 201 | Chain Reaction              | Refactoria     | medium     | 30     |
| 202 | Trust, but Verify           | Refactoria     | medium     | 35     |
| 203 | The Full Build              | Refactoria     | medium     | 35     |
| 301 | Selective Operations        | Selectoria     | medium     | 30     |
| 302 | Custom Tests                | Selectoria     | hard       | 55     |
| 401 | Documentation Station       | Documentum     | medium     | 30     |
| 402 | The Macro Workshop          | Documentum     | hard       | 60     |
| 501 | Materializations & Ghosts   | Materia        | medium     | 30     |
| 502 | Schema Mastery              | Materia        | hard       | 50     |
| 601 | Snapshot: Freeze Frame      | Tempus         | hard       | 60     |
| 602 | Incremental                 | Tempus         | hard       | 65     |
| 701 | The Line-Item Fact          | Marsius        | hard       | 60     |
| 702 | RFM Segments                | Marsius        | expert     | 90     |
| 703 | The Marketing Funnel        | Marsius        | expert     | 90     |

**Total: 775 credits across 17 challenges.**

Good luck, contestant. Use `scan` when you're stuck; use `skip` if you need to come back later; use `quit` and your progress is saved.
