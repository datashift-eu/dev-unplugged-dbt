# Maintainer Playthrough — Masterkey

The complete organizer's reference. For every challenge this document
contains:

- The verbatim contestant prompt (description block) — what the player sees first
- All hints (revealed one-by-one when the player types `scan`; each costs 10% of points)
- The validator JS that ships in `src/challenges.js` (including diagnostic wrong-answer branches)
- The reference file changes (idiomatic dbt 1.11, sqlfluff-clean)
- The build command
- The validation query that computes the answer
- The answer itself
- Why the answer is what it is
- Bonus tracks and maintainer notes where applicable

Use it for: onboarding co-organizers, populating `__ANS__` placeholders in
`voyager_challenges.md` validators, helping a stuck contestant when a hint
isn't landing, sanity-checking after any change to `starter.duckdb`.

**Not for contestants.** Exclude `docs/` from any distribution shipped to
workshop attendees.

All answers re-verified against `starter.duckdb` on 2026-05-25.

---

## Planet 1 — Terra Stagia

### Challenge 101 — First Light

**Difficulty:** easy · **Points:** 15 · **Answer:** `42`

#### Contestant prompt

> A starter dbt project lands on your desk with one model in it,
> and that model is broken. It won't even parse.
>
> First task: make it work. Then make it good.
>
> "Good" is what staging models exist for: rename source columns to
> domain-friendly names, lock down types, and normalize messy values.
> Take a look at the raw customer table — particularly the country
> column. You'll notice the source system isn't consistent about how
> it writes the same country (which is exactly the kind of mess that
> staging exists to clean up).
>
> **Business question:** how many of your customers are based in the
> Netherlands?

#### Hints

1. dbt builds your models with `dbt run`. The `justfile` wraps the common commands — try `just --list`.
2. Look at the distinct country values in `raw_customers`. There are four representations of the same country.
3. `UPPER(TRIM(country))` collapses the four variants into one canonical value.

#### Files changed

`models/staging/stg_customers.sql` *(modify)*:

```sql
SELECT
    id                          AS customer_id,
    first_name,
    last_name,
    LOWER(email)                AS email,
    UPPER(TRIM(country))        AS country,
    CAST(created_at AS DATE)    AS created_date
FROM raw_customers
```

#### Build

```bash
just run --select stg_customers
```

#### Validation query

```sql
SELECT COUNT(*) FROM stg_customers WHERE country = 'NL';
```

#### Validator (`src/challenges.js`)

```js
async validator(answer) {
  const g = asInt(answer);
  if (g === 42)             return { ok: true,  message: "42 ✓ — staging normalization works." };
  if (g === 25)             return { ok: false, message: "That's the count from raw without any normalization." };
  if (g === 33 || g === 29) return { ok: false, message: "Closer — TRIM as well as UPPER. Leading/trailing spaces still leak through." };
  return { ok: false, message: `Got ${g}. Expected the count of customers in the Netherlands.` };
}
```

#### Why this works

The raw `country` column has four representations of NL (`'NL'`, `'nl'`,
`' NL '`, `'NL '`). Querying raw with `country = 'NL'` returns only 25.
`UPPER(TRIM(country))` collapses all four into the canonical `'NL'`,
revealing the seeded total of 42.

---

### Challenge 102 — Know Your Sources

**Difficulty:** easy · **Points:** 20 · **Answer:** `2`

#### Contestant prompt

> Your staging model currently reads from a hardcoded raw table name.
> That's a brittle pattern: dbt can't see the lineage, nobody can
> monitor source freshness, and a rename in the source system means
> hunting every FROM clause in the project.
>
> dbt has a first-class way to declare external (raw) tables and
> reference them — use it. Convert the existing model to that pattern,
> declare every raw business table your staging models touch, and add
> a second staging model — for orders, at `models/staging/stg_orders.sql`
> — exposing order_id, customer_id, amount, status, and the order date
> (cast properly).
>
> Once everything's wired, this command lists the model resources
> downstream of your declared source (i.e. the blast radius if any raw
> business table changed):
>
>     just dbt ls --quiet --select source:jaffle_shop+ --resource-type model
>
> **Business question:** how many models does it list?
>
> Docs: https://docs.getdbt.com/docs/build/sources

#### Hints

1. The dbt concept is "sources". Declarations live in a YAML file inside `models/` — the conventional name is `_sources.yml`.
2. In SQL, you reference a source with the `source()` jinja function instead of a hardcoded table name.
3. If the count surprises you, your conversion to `{{ source() }}` might be incomplete — search the project for any remaining hardcoded `raw_` references in FROM clauses.

#### Files changed

`models/staging/_sources.yml` *(modify — extend the partial file already in the project)*:

```yaml
version: 2

sources:
  - name: jaffle_shop
    description: "Raw operational data from the jaffle shop business systems."
    schema: main
    tables:
      - name: raw_customers
      - name: raw_orders
      - name: raw_payments
```

`models/staging/stg_customers.sql` *(modify — swap hardcoded FROM for `source()`)*:

```sql
SELECT
    id                          AS customer_id,
    first_name,
    last_name,
    LOWER(email)                AS email,
    UPPER(TRIM(country))        AS country,
    CAST(created_at AS DATE)    AS created_date
FROM {{ source('jaffle_shop', 'raw_customers') }}
```

`models/staging/stg_orders.sql` *(replace the typed stub)*:

```sql
SELECT
    id                          AS order_id,
    customer_id,
    amount,
    status,
    CAST(ordered_at AS DATE)    AS ordered_date
FROM {{ source('jaffle_shop', 'raw_orders') }}
```

#### Build

```bash
just build --select staging
```

#### Validation query (selector)

```bash
just dbt ls --quiet --select source:jaffle_shop+ --resource-type model
```

#### Validator (`src/challenges.js`)

```js
async validator(answer) {
  const g = asInt(answer);
  if (g === 2) return { ok: true,  message: "2 ✓ — sources are wired and lineage is intact." };
  if (g === 0) return { ok: false, message: "Zero means dbt doesn't see the dependency. Your model is probably still using a hardcoded FROM." };
  return { ok: false, message: `Got ${g}. Expected the count of models downstream of the raw business tables.` };
}
```

#### Why this works

Counting the output: `stg_customers` and `stg_orders` both list as
downstream of `source:jaffle_shop`. `stg_payments` doesn't exist yet
(comes in 103). Answer = 2. Including the literal selector command in
the prompt forces contestants to actually run it (rather than guessing
"2" from project structure alone) AND teaches the selector mechanic
as a side effect.

---

### Challenge 103 — The Seed Vault

**Difficulty:** easy · **Points:** 20 · **Answer:** `3193396.14`

#### Contestant prompt

> Some reference data isn't raw source data — it's small, slow-changing,
> and owned by your team. A four-row mapping of payment methods to their
> display names and processing fees is a perfect example. It doesn't
> belong in raw_X (no source system produced it) and it doesn't belong
> inside a model (it's data, not logic).
>
> dbt has a separate mechanism for team-owned reference data. **First**,
> get the finance team's mapping into the project — header row and four
> data rows, exactly as below:
>
>     payment_method,payment_method_name,processing_fee_pct
>     credit_card,Credit Card,2.9
>     coupon,Coupon,0.0
>     bank_transfer,Bank Transfer,0.5
>     gift_card,Gift Card,0.0
>
> After loading, take a quick look in your database — the mapping
> should now exist as a real table in `main`, just like a raw_X table
> would. You won't use it from a model yet (that join belongs in the
> intermediate layer, which is the next planet), but it's persisted
> and ready.
>
> **Second**, build stg_payments at `models/staging/` — pure staging
> only, no joins, no enrichment. It should expose payment_id, order_id,
> payment_method, and the payment amount converted into dollars.
>
> (You'll also notice the project ships with another seed file,
> `iso_country_codes.csv` — that's for a much later challenge. Leave
> it alone for now.)
>
> **Business question:** how many dollars of revenue have come through
> bank transfers across all time?
>
> Docs: https://docs.getdbt.com/docs/build/seeds

#### Hints

1. The dbt concept is "seeds". They live in a `seeds/` folder as CSVs, and dbt has a dedicated command to load them.
2. Look in `raw_payments` to see what currency unit the `amount` column is in. (Hint: it's not dollars.)
3. Watch for integer division — `amount / 100` and `amount / 100.0` produce different answers.

#### Files changed

`seeds/payment_method_mapping.csv` *(new)*:

```csv
payment_method,payment_method_name,processing_fee_pct
credit_card,Credit Card,2.9
coupon,Coupon,0.0
bank_transfer,Bank Transfer,0.5
gift_card,Gift Card,0.0
```

`models/staging/stg_payments.sql` *(new)* — pure staging, no joins:

```sql
SELECT
    id                              AS payment_id,
    order_id,
    payment_method,
    ROUND(amount / 100.0, 2)        AS amount_dollars
FROM {{ source('jaffle_shop', 'raw_payments') }}
```

#### Build

```bash
just seed
just run --select stg_payments
```

#### Validation query

```sql
SELECT ROUND(SUM(amount_dollars), 2)
FROM stg_payments
WHERE payment_method = 'bank_transfer';
```

#### Validator (`src/challenges.js`)

```js
async validator(answer) {
  const g = asFloat(answer, 2);
  if (g === 3193396.14) return { ok: true,  message: `$${g} ✓` };
  return { ok: false, message: `Got ${g}. Round to 2 decimals; check your cents→dollars conversion.` };
}
```

#### Why this works

`/ 100.0` not `/ 100` (the `.0` forces float division). Summing across
the `bank_transfer` slice of the seeded payments yields exactly
$3,193,396.14.

---

## Planet 2 — Refactoria

### Challenge 201 — Chain Reaction

**Difficulty:** medium · **Points:** 30 · **Answer:** `8584`

#### Contestant prompt

> Staging models should stay 1:1 with source — no joins, no enrichment.
> That work belongs in an intermediate layer. The intermediate is where
> you start combining things: joining the team-owned mapping seed onto
> the staging payments, aggregating to a more useful grain.
>
> Build `int_payments` at `models/intermediate/`. Grain: one row per
> unique (order_id, payment_method_name) — so an order paid partly by
> credit card and partly by coupon yields two rows. Each row should
> expose the order_id, the human-readable payment_method_name (from
> the seed — not the raw code), the total dollar amount paid by that
> method on that order, and the count of payment events that make up
> that total. The default materialization for intermediate models in
> this project is `view`.
>
> **Business question:** how many orders in your warehouse were paid using
> more than one distinct payment method?
>
> Docs: https://docs.getdbt.com/reference/dbt-jinja-functions/ref

#### Hints

1. The dbt function to reference another model (or a seed) is `ref()`. It works for both — the seed name is the CSV filename without `.csv`.
2. LEFT JOIN, not INNER — a payment whose method isn't in the mapping shouldn't disappear from the totals.
3. The raw `payment_method` code column shouldn't appear in your output once you have the display name.

#### Files changed

`models/intermediate/int_payments.sql` *(new)*:

```sql
WITH payments AS (
    SELECT * FROM {{ ref('stg_payments') }}
),

mapping AS (
    SELECT * FROM {{ ref('payment_method_mapping') }}
)

SELECT
    p.order_id,
    m.payment_method_name,
    m.processing_fee_pct,
    SUM(p.amount_dollars)   AS total_amount,
    COUNT(*)                AS payment_count
FROM payments AS p
LEFT JOIN mapping AS m
    ON p.payment_method = m.payment_method
GROUP BY p.order_id, m.payment_method_name, m.processing_fee_pct
```

#### Build

```bash
just run --select int_payments
```

#### Validation query

```sql
SELECT COUNT(*)
FROM (
    SELECT order_id
    FROM int_payments
    GROUP BY order_id
    HAVING COUNT(*) > 1
);
```

#### Validator (`src/challenges.js`)

```js
async validator(answer) {
  const g = asInt(answer);
  if (g === 8584) return { ok: true,  message: "8584 ✓ — intermediate aggregation works." };
  if (g === 0)    return { ok: false, message: "Zero — your grain is probably one row per order (collapsed), not one row per (order, payment_method)." };
  return { ok: false, message: `Got ${g}. Count orders that appear with more than one distinct payment_method_name.` };
}
```

#### Why this works

`int_payments` is at `(order_id, payment_method_name)` grain. Orders
paid by multiple methods appear in multiple rows. Counting orders that
appear more than once = 8,584 multi-method orders.

---

### Challenge 202 — Trust, but Verify

**Difficulty:** medium · **Points:** 35 · **Answer:** `3`

#### Contestant prompt

> Data without tests is just vibes. dbt has a built-in test framework
> for declarative, reusable assertions about your models — uniqueness,
> non-nullness, referential integrity, allowed value sets.
>
> Add tests that capture the obvious invariants of your staging models:
> primary keys are unique and non-null, foreign keys actually reference
> something that exists, and status values come from a known short list
> (completed, pending, cancelled). When you run them, at least two will
> fail — and the failures point at real issues the staging layer should
> clean up. Don't fix them yet; just investigate.
>
> **Business question:** how many orders in your project reference a customer
> that doesn't exist?
>
> Docs: https://docs.getdbt.com/docs/build/data-tests

#### Hints

1. Tests are declared in a YAML file next to the models. Convention is `_schema.yml` (or `models.yml`).
2. The four most common built-in tests are `unique`, `not_null`, `accepted_values`, and `relationships`. In dbt 1.11+, parameterized tests use a nested `arguments:` block.
3. To find the orphans yourself: LEFT JOIN orders to customers on customer_id, count rows where the customer side comes back NULL.

#### Files changed

`models/staging/_models.yml` *(new)*:

```yaml
version: 2

models:
  - name: stg_customers
    columns:
      - name: customer_id
        data_tests: [unique, not_null]

  - name: stg_orders
    columns:
      - name: order_id
        data_tests: [not_null]
      - name: customer_id
        data_tests:
          - relationships:
              arguments:
                to: ref('stg_customers')
                field: customer_id
      - name: status
        data_tests:
          - accepted_values:
              arguments:
                values: ['completed', 'pending', 'cancelled']

  - name: stg_payments
    columns:
      - name: payment_id
        data_tests: [not_null]
```

#### Build

```bash
just test
```

#### Validation query

```sql
SELECT COUNT(*)
FROM stg_orders AS o
LEFT JOIN stg_customers AS c USING (customer_id)
WHERE c.customer_id IS NULL;
```

#### Validator (`src/challenges.js`)

```js
async validator(answer) {
  const g = asInt(answer);
  if (g === 3) return { ok: true,  message: "3 ✓ — three orphan orders." };
  if (g === 0) return { ok: false, message: "Zero means your join is INNER (or the filter is inverted). LEFT JOIN, then keep the NULLs." };
  return { ok: false, message: `Got ${g}. Expected the count of orders whose customer_id has no match in customers.` };
}
```

#### Maintainer note

`starter.duckdb` must contain (a) three orphan orders with
customer_ids `99901–99903` and (b) at least one order with
`status = 'pending '` (trailing space). Verified present in
`scripts/generate_starter_db.py` and in `starter.duckdb` as of
2026-05-25. If either ever drifts, this challenge silently passes and
203 stops being meaningful.

#### Why this works

Three orphan orders are seeded into `raw_orders` (customer_ids
99901–99903) with no match in `raw_customers`. The `relationships`
test fires with exactly 3 failing rows. The `accepted_values` test
also fails because one order has `'pending '` (trailing space). The
contestant identifies but doesn't fix — that's 203's job.

> **Note on 202 vs 203:** the answer to 203 is *also* `3`. That's
> intentional: 202 asks the contestant to identify the broken rows,
> 203 asks them to verify the cleanup dropped those exact rows. Same
> number on both sides = proof they found and fixed precisely the
> right rows. Don't change one without changing the other in lockstep.

---

### Challenge 203 — The Full Build

**Difficulty:** medium · **Points:** 35 · **Answer:** `3`

#### Contestant prompt

> The two failures from the previous challenge both belong to the orders
> staging model. That's not a coincidence — cleaning conformance issues
> so downstream consumers can trust the data is exactly what the staging
> layer is for.
>
> Fix the orders staging model so that orphan orders disappear and the
> status values conform to the allowed set. Drop orphans via an INNER
> JOIN on `ref('stg_customers')` (i.e. join staging → staging, not
> staging → source). Earlier challenges emphasized "staging stays 1:1
> with source, no joins" — referential-integrity conformance against
> another staging model is the canonical exception, and using `ref()`
> keeps the lineage visible to dbt.
>
> Then run a single dbt command that rebuilds models in dependency
> order AND runs every test, and confirm everything passes.
>
> **Business question:** after your cleanup, how many orders did your model
> drop compared to raw?

#### Hints

1. Dropping orphans is one JOIN choice; trimming dirty values is a string function on the column. Both happen inside the staging model.
2. dbt has a command that combines `run` and `test` and respects the DAG — look for it in `dbt --help`.
3. If a test still fails after your fix, dbt prints the exact failing-rows SQL — copy it and run it to see which value still violates.

#### Files changed

`models/staging/stg_orders.sql` *(modify)*:

```sql
WITH source AS (
    SELECT
        id                          AS order_id,
        customer_id,
        amount,
        TRIM(status)                AS status,
        CAST(ordered_at AS DATE)    AS ordered_date
    FROM {{ source('jaffle_shop', 'raw_orders') }}
),

customers AS (
    SELECT customer_id FROM {{ ref('stg_customers') }}
)

SELECT s.*
FROM source AS s
INNER JOIN customers AS c USING (customer_id)
```

#### Build

```bash
just build
```

#### Validation query

```sql
SELECT (SELECT COUNT(*) FROM raw_orders) - (SELECT COUNT(*) FROM stg_orders);
```

#### Validator (`src/challenges.js`)

```js
async validator(answer) {
  const g = asInt(answer);
  if (g === 3) return { ok: true,  message: "3 ✓ — orphans gone, tests pass." };
  return { ok: false, message: `Got ${g}. After cleanup, compare row counts in raw_orders vs. your staging model.` };
}
```

#### Why this works

INNER JOIN drops the 3 orphans; `TRIM` collapses `'pending '` into
`'pending'`. All six staging tests now pass. The raw-vs-staging row
delta is exactly 3 — proof the cleanup hit exactly the orphans 202
identified.

---

## Planet 3 — Selectoria

### Challenge 301 — Selective Operations

**Difficulty:** medium · **Points:** 30 · **Answer:** `1`

#### Contestant prompt

> In real projects, you don't run every model on every change — you run
> exactly the subset that matters. dbt's selector language is the tool:
> graph operators for upstream/downstream, intersection for "models that
> are both X and Y", resource-type filters, source selectors.
>
> The question you'll answer is one analytics engineers ask whenever
> a model is about to change: who downstream depends on me? At four
> models you could trace it by hand, at four hundred you cannot — so
> build the muscle now.
>
> **Business question:** using only `dbt ls` with selectors (no SQL, no
> opening project files), how many model resources depend on
> `stg_payments` — NOT counting `stg_payments` itself?

#### Hints

1. The selector language reference is at https://docs.getdbt.com/reference/node-selection/syntax. Look for graph operators, resource types, AND the exclude flag.
2. A trailing `+` after a node name means "everything downstream of this node, transitively, including the node itself".
3. Restrict the answer to models only with `--resource-type model`. Without it, tests defined on those models inflate the count.
4. To strip the model itself from the result set, use `--exclude stg_payments`.

#### Files changed

None — pure selector usage.

#### Validation query (selector)

```bash
just dbt ls --quiet \
    --select stg_payments+ \
    --exclude stg_payments \
    --resource-type model
```

#### Validator (`src/challenges.js`)

```js
async validator(answer) {
  const g = asInt(answer);
  if (g === 1) return { ok: true,  message: "1 ✓ — only int_payments depends on stg_payments." };
  if (g === 2) return { ok: false, message: "2 — you probably included stg_payments itself. Use --exclude to drop it." };
  if (g === 0) return { ok: false, message: "Zero — you're missing the `+` operator after stg_payments." };
  return { ok: false, message: `Got ${g}. Expected count of models downstream of stg_payments, excluding the model itself.` };
}
```

#### Why this works

After 201, only `int_payments` depends on `stg_payments`. The
inclusive `+` selector would return 2 (stg_payments itself plus
int_payments); `--exclude stg_payments` strips the self-reference,
landing on 1. `--resource-type model` strips any tests defined on
either model.

---

### Challenge 302 — Custom Tests

**Difficulty:** hard · **Points:** 55 · **Answer:** `1`

#### Contestant prompt

> Built-in tests cover the obvious invariants. Real projects need custom
> ones. dbt supports two flavours: GENERIC tests (reusable across models,
> parameterized by model + column) and SINGULAR tests (one-off assertions
> specific to a single piece of business logic).
>
> Write one of each.
>
> > **Generic:** an `is_positive` test that fails when a column's value is
> > ≤ 0. Apply it to the total amount on your intermediate payments
> > model. Heads up: this test WILL fail — your intermediate has
> > legitimate zero-amount rows for coupon-paid orders. That's the
> > pedagogical moment. In a real project you'd either tighten the test
> > to `< 0` or treat zero as a quality violation; for the challenge,
> > leave the failure visible.
> >
> > **Singular:** a quality check on the product reviews. A 5-star review
> > whose text contains the word "terrible" (case-insensitive) is almost
> > certainly miscategorized — surface those.
>
> A dbt test passes when its SELECT returns zero rows. The puzzle
> below asks how many rows your singular test returns (i.e., how many
> violations it surfaces), NOT whether it passes.
>
> **Business question:** how many "5-star terrible" reviews exist in the
> review data?

#### Hints

1. Generic tests: https://docs.getdbt.com/best-practices/writing-custom-generic-tests. Singular tests: https://docs.getdbt.com/docs/build/data-tests#singular-data-tests.
2. Generic tests live in `tests/generic/`; singular tests live directly in `tests/`. The two file shapes are different — read both doc pages.
3. Apply your generic test the same way you apply built-in ones — in the model's YAML, under `tests:` on the column.

#### Files changed

`tests/generic/test_is_positive.sql` *(new)*:

```jinja
{% test is_positive(model, column_name) %}

SELECT {{ column_name }}
FROM {{ model }}
WHERE {{ column_name }} <= 0

{% endtest %}
```

`models/intermediate/_models.yml` *(new)*:

```yaml
version: 2

models:
  - name: int_payments
    columns:
      - name: total_amount
        data_tests:
          - is_positive
```

`models/staging/_sources.yml` *(modify — add raw_reviews)*:

```yaml
      - name: raw_reviews
```

`tests/assert_no_five_star_terribles.sql` *(new)*:

```sql
SELECT
    id,
    rating,
    review_text
FROM {{ source('jaffle_shop', 'raw_reviews') }}
WHERE rating = 5
  AND LOWER(review_text) LIKE '%terrible%'
```

#### Build

```bash
just test --select test_type:singular
```

#### Validation query

```sql
SELECT COUNT(*)
FROM raw_reviews
WHERE rating = 5
  AND LOWER(review_text) LIKE '%terrible%';
```

#### Validator (`src/challenges.js`)

```js
async validator(answer) {
  const g = asInt(answer);
  if (g === 1) return { ok: true,  message: "1 ✓ — exactly one quality violation seeded." };
  if (g === 0) return { ok: false, message: "Zero — case sensitivity. Apply LOWER() before matching." };
  return { ok: false, message: `Got ${g}. Expected the count of 5-star reviews whose text contains 'terrible'.` };
}
```

#### Why this works

The seed plants exactly one 5-star review whose text contains
"terrible". The singular test surfaces that one row. The `is_positive`
test also fails (on legitimate $0 coupon rows) — that's the lesson, not
a bug.

---

## Planet 4 — Documentum

### Challenge 401 — Documentation Station

**Difficulty:** medium · **Points:** 30 · **Answer:** `4` *(see note)*

#### Contestant prompt

> If it isn't documented, it doesn't exist. dbt turns the descriptions
> you write in YAML into a navigable docs site with lineage diagrams,
> column-level metadata, and search.
>
> Add a model-level description for every model you've built so far
> (stage models plus the intermediate). Pick the most ambiguous columns
> in each model — the ones a new analyst would Slack you about — and
> describe them too. Generate the docs site and browse the lineage view
> for your intermediate model. Confirm the graph reaches all the way
> back to raw.
>
> **Business question:** how many of your models have a model-level
> description set?
>
> Docs: https://docs.getdbt.com/reference/resource-properties/description

#### Hints

1. Descriptions go in the same YAML file as your tests. The `description:` key sits at the same level as `tests:`.
2. After editing YAML, dbt has to re-parse before the manifest reflects your changes. The docs-generate command does this automatically.
3. The puzzle reads `target/manifest.json`. The container has `python3` and `duckdb` — both can parse JSON. Count nodes where `resource_type == 'model'` and `description` is non-empty.

#### Files changed

`models/staging/_models.yml` *(modify — add `description:` to each model + at least 2 column descriptions per model)*:

```yaml
version: 2

models:
  - name: stg_customers
    description: "One row per customer. Canonicalized country codes; emails lowercased."
    columns:
      - name: customer_id
        description: "Surrogate PK from the source `id` column."
        data_tests: [unique, not_null]
      - name: country
        description: "ISO 3166-1 alpha-2 country code, normalized (UPPER + TRIM)."

  - name: stg_orders
    description: "One row per order, post-cleanup. Orphan orders dropped; status trimmed."
    columns:
      - name: order_id
        description: "Surrogate PK from the source `id` column."
        data_tests: [not_null]
      - name: status
        description: "Order lifecycle status — one of completed, pending, cancelled."
        data_tests:
          - accepted_values:
              arguments:
                values: ['completed', 'pending', 'cancelled']
      - name: customer_id
        data_tests:
          - relationships:
              arguments:
                to: ref('stg_customers')
                field: customer_id

  - name: stg_payments
    description: "One row per payment event. Cents converted to dollars."
    columns:
      - name: payment_id
        description: "Surrogate PK from the source `id` column."
        data_tests: [not_null]
      - name: amount_dollars
        description: "Payment amount in dollars (raw cents / 100, 2dp)."
```

`models/intermediate/_models.yml` *(modify — add description for `int_payments`)*:

```yaml
version: 2

models:
  - name: int_payments
    description: "One row per (order, payment method). Total dollars and event count for each combination."
    columns:
      - name: total_amount
        description: "Sum of `amount_dollars` for this (order_id, payment_method_name)."
        data_tests:
          - is_positive
      - name: payment_count
        description: "Number of payment events that make up `total_amount`."
```

#### Build

```bash
just docs
```

#### Validation query (Python — no jq in container)

```bash
python3 -c "import json; m=json.load(open('target/manifest.json')); \
print(sum(1 for n in m['nodes'].values() \
if n['resource_type']=='model' and n['description']))"
```

#### Validator (`src/challenges.js`)

```js
async validator(answer) {
  const g = asInt(answer);
  if (g === 4) return { ok: true,  message: "4 ✓ — every model is documented." };
  if (g < 4)   return { ok: false, message: `${g}/4 — some models are still missing a model-level description.` };
  return { ok: false, message: `Got ${g}. Expected one per model.` };
}
```

#### Note on the answer

The puzzle answer reflects *how many models the contestant actually
added a description to*. If they follow the prompt ("every model you've
built so far"), that's the four models in scope at this point of the
playthrough: `stg_customers`, `stg_orders`, `stg_payments`,
`int_payments` → 4. A contestant who only describes some of them gets a
diagnostic count from the validator (`X/4`); only `4` passes. Holding
contestants to the spec is intentional — this is a discipline lesson.

#### Bonus (optional)

`dbt-osmosis` propagates column descriptions from upstream to
downstream automatically. Install with `uv add dbt-osmosis` and try it
on your intermediate model. Column descriptions you wrote on staging
will cascade.

---

### Challenge 402 — The Macro Workshop

**Difficulty:** hard · **Points:** 60 · **Answer:** `d4dfe0d3`

#### Contestant prompt

> You've already written `amount / 100.0` once. If you write it again
> somewhere else, you've started repeating yourself — and the day someone
> changes the convention you'll be hunting every instance. Extract it
> into a macro.
>
> Build two macros. The first wraps cents-to-dollars conversion: takes
> a column name and returns the SQL fragment
> `ROUND(CAST(<col> AS DECIMAL) / 100.0, 2)` (rounded to two decimal
> places — same precision as Challenge 103, so the downstream answers
> don't drift). Use it in stg_payments to replace the inline calculation.
>
> The second is a surrogate-key generator that MD5-hashes a list of
> fields. Specifications you need to follow exactly so the hash is
> deterministic:
>
> > - Fields, in order:    `[order_id, payment_id]`
> > - Cast each field:     `CAST(<field> AS VARCHAR)` **before** the COALESCE.
> >                        order_id is an INTEGER — COALESCE can't mix an
> >                        integer with the `'_null_'` string sentinel, so
> >                        the cast has to happen first or you'll hit a
> >                        type-mismatch error.
> > - Separator:           the literal pipe character `'|'`
> > - NULL sentinel:       COALESCE NULL → the literal string `'_null_'`
> >                        (so (NULL,'x') doesn't collide with (NULL,NULL))
> > - Output:              MD5 of the joined string, lowercase hex
>
> Give the macro the exact same name as the surrogate-key macro in
> dbt_utils (`generate_surrogate_key`). Add a `payment_key` column to
> stg_payments by calling it UNQUALIFIED — i.e.
> `{{ generate_surrogate_key(['order_id', 'payment_id']) }}` — and
> observe which implementation wins. (Two name-resolution rules to
> understand: unqualified macro calls resolve to your project's macros
> first; the separate `dispatch` config is what would force calls
> written as `dbt_utils.generate_surrogate_key(...)` through your
> override too. The puzzle only requires the unqualified path — try
> dispatch as a bonus.)
>
> There's a SQL scoping gotcha: the column you hash on is a SELECT alias
> of a source column. Most engines can't reference a SELECT alias from
> another expression in the same SELECT — structure with a CTE so the
> rename is in scope before the macro call.
>
> **Business question:** what are the first 8 characters of the payment_key
> for payment_id = 1?
>
> Docs: https://docs.getdbt.com/docs/build/jinja-macros

#### Hints

1. Macro syntax is `{% macro name(args) %}...{% endmacro %}`. The body is the SQL fragment that gets inlined where you call the macro.
2. For the surrogate key: a `{% for %}` loop that emits `COALESCE(CAST(field AS VARCHAR), '_null_')` per field, joined by `' || "|" || '`, all wrapped in `MD5(...)`.
3. dbt resolves an unqualified macro call by searching your project first, then installed packages — that's why same-name shadowing works.
4. For the `dispatch` mechanism (bonus, to force *all* references through your override even from package-internal callers): https://docs.getdbt.com/reference/dbt-jinja-functions/dispatch

#### Files changed

`macros/cents_to_dollars.sql` *(new)*:

```jinja
{% macro cents_to_dollars(column_name) %}
    ROUND(CAST({{ column_name }} AS DECIMAL) / 100.0, 2)
{% endmacro %}
```

`macros/generate_surrogate_key.sql` *(new — shadows dbt_utils)*:

```jinja
{% macro generate_surrogate_key(field_list) %}
    MD5(
        {%- for f in field_list %}
        COALESCE(CAST({{ f }} AS VARCHAR), '_null_')
        {%- if not loop.last %} || '|' || {%- endif %}
        {%- endfor %}
    )
{% endmacro %}
```

`models/staging/stg_payments.sql` *(modify — use both macros)*:

```sql
WITH source AS (
    SELECT
        id              AS payment_id,
        order_id,
        payment_method,
        amount
    FROM {{ source('jaffle_shop', 'raw_payments') }}
)

SELECT
    payment_id,
    order_id,
    payment_method,
    {{ cents_to_dollars('amount') }}                            AS amount_dollars,
    {{ generate_surrogate_key(['order_id', 'payment_id']) }}    AS payment_key
FROM source
```

#### Build

```bash
just run --select stg_payments
```

#### Validation query

```sql
SELECT LEFT(payment_key, 8) FROM stg_payments WHERE payment_id = 1;
```

#### Validator (`src/challenges.js`)

```js
async validator(answer) {
  const a = answer.trim().toLowerCase();
  if (!/^[a-f0-9]{8}$/.test(a)) {
    return { ok: false, message: "Expected an 8-character lowercase hex string." };
  }
  if (a === "d4dfe0d3") return { ok: true, message: `${a} ✓ — local macro shadowed dbt_utils.` };
  return { ok: false, message: "Right shape, wrong hash. Check your separator ('|') and the NULL sentinel." };
}
```

#### Why this works

For `payment_id = 1`, `order_id = 1` (verified directly via
`SELECT order_id FROM raw_payments WHERE id = 1`). After the CAST +
COALESCE round-trip, the literal string fed to MD5 is `1|1`.
`MD5('1|1') = 'd4dfe0d3...'` — first 8 chars are `d4dfe0d3`.

#### Bonus — dispatch

Try `{{ dbt_utils.generate_surrogate_key(['order_id', 'payment_id']) }}`
explicitly (different hash, because dbt_utils uses `'-'` as separator).
To force *all* calls to `dbt_utils.generate_surrogate_key` through your
override (including package-internal callers), configure
`dbt_project.yml`:

```yaml
dispatch:
  - macro_namespace: dbt_utils
    search_order: ["dbt_escape_room", "dbt_utils"]
```

Flip the search order, re-run, observe the hash change.

---

## Planet 5 — Materia

### Challenge 501 — Materializations & Ghost Objects

**Difficulty:** medium · **Points:** 30 · **Answer:** `4`

#### Contestant prompt

> Not every model should be a database table. Views save space but cost
> query time. Ephemeral models exist only as CTEs inlined into downstream
> queries. Tables cost storage but speed up reads. The right choice
> depends on the model's place in the pipeline.
>
> Reconfigure the project so staging models stay as views, intermediate
> models become ephemeral, and marts (which you'll start building in a
> later planet) materialize as tables. Then rebuild and look closely at
> what objects actually exist in the database.
>
> There's a gotcha here that catches every dbt newcomer once. Find it
> — and DO NOT clean it up yet; the puzzle answer depends on observing
> the world as dbt left it.
>
> **Business question:** immediately after your reconfigure-and-rebuild
> (no manual cleanup), how many views exist in the main schema?
>
> Docs: https://docs.getdbt.com/docs/build/materializations

#### Hints

1. Materializations are configured under `models:` in `dbt_project.yml` with the `+materialized:` key. They can be set per folder.
2. Ephemeral models don't exist as DB objects at all — they're inlined wherever a downstream model `ref()`s them.
3. The gotcha: dbt is *additive*. When you change a model's materialization, the previous incarnation of that model isn't dropped. It hangs around as a "ghost" until someone manually cleans it up.

#### Files changed

`dbt_project.yml` *(modify — flip intermediate from `view` to `ephemeral`)*:

```yaml
models:
  "dbt_escape_room":
    staging:
      +materialized: view
      +tags: ["staging"]
    intermediate:
      +materialized: ephemeral
      +tags: ["intermediate"]
    marts:
      +materialized: table
      +tags: ["marts"]
```

#### Build

```bash
just build
```

#### Validation query

```sql
SELECT COUNT(*)
FROM information_schema.tables
WHERE table_schema = 'main' AND table_type = 'VIEW';
```

#### Validator (`src/challenges.js`)

```js
async validator(answer) {
  const g = asInt(answer);
  if (g === 4) return { ok: true,  message: "4 ✓ — 3 staging views plus one ghost." };
  if (g === 3) return { ok: false, message: "3 means you (or someone) already dropped the ghost. Check before cleanup." };
  return { ok: false, message: `Got ${g}. Expect 4: three staging views plus the ghost from the intermediate's previous materialization.` };
}
```

#### Why this works

After flipping `intermediate` to `ephemeral`, dbt no longer manages
`int_payments` as a DB object — but it didn't drop the old view. Three
staging views (managed) + one ghost = 4. After the contestant runs
`DROP VIEW int_payments;` the count drops to 3.

---

### Challenge 502 — Schema Mastery

**Difficulty:** hard · **Points:** 50 · **Answer:** `main_marts`

#### Contestant prompt

> Beyond toy projects, models land in multiple schemas: marts in `marts`,
> snapshots in `snapshots`, raw mirrors in `raw`. dbt has a `+schema:`
> config for this. The default behaviour is famously surprising — every
> team in production ends up overriding it.
>
> Set up the project so that any future marts models will land in a
> `marts` schema and snapshots will land in a `snapshots` schema. Note
> that marts configuration sits under `models:` in `dbt_project.yml`,
> but snapshot configuration sits under a separate top-level
> `snapshots:` block (and uses the key `+target_schema`, not `+schema`)
> — easy to miss. Then, before the override takes effect everywhere,
> investigate what dbt would have produced *by default* if no override
> existed.
>
> To actually observe the default schema in action, the marts folder
> needs at least one model (otherwise there's nothing for the schema
> config to materialize). Create a tiny throwaway probe model under
> `models/marts/` (one row of anything) — you'll delete it after the
> challenge. There's a macro in this project that handles the override
> — temporarily disable it (rename to `.bak`), re-parse or rebuild your
> probe, observe the schema dbt actually uses, then restore the macro
> and delete the probe.
>
> **Business question:** with the override disabled, what schema would dbt
> produce for a marts-configured model when the target schema is `main`?
> Format: lowercase, single underscore.
>
> Docs: https://docs.getdbt.com/docs/build/custom-schemas

#### Hints

1. The override mechanism is a macro named `generate_schema_name`. dbt looks for one in your project before falling back to its own.
2. To disable it temporarily without losing it, rename the file to `.bak` and re-parse. Restore after.
3. The container has no `jq`. To read the schema dbt actually used for any marts-configured node, parse the manifest with Python from the project root:

       python3 -c "import json; m=json.load(open('target/manifest.json')); print({n['name']: n['schema'] for n in m['nodes'].values() if n.get('config', {}).get('schema') == 'marts'})"

#### Files changed

`dbt_project.yml` *(modify — add `+schema: marts` for marts AND a separate top-level `snapshots:` block with `+target_schema`)*:

```yaml
models:
  "dbt_escape_room":
    staging:
      +materialized: view
      +tags: ["staging"]
    intermediate:
      +materialized: ephemeral
      +tags: ["intermediate"]
    marts:
      +schema: marts
      +materialized: table
      +tags: ["marts"]

snapshots:
  "dbt_escape_room":
    +target_schema: snapshots
```

`models/marts/_probe.sql` *(new — throwaway, delete after the challenge)*:

```sql
SELECT 1 AS probe
```

#### Build (with override macro temporarily disabled)

```bash
mv macros/generate_schema_name.sql macros/generate_schema_name.sql.bak
just dbt parse
# Read the manifest using the Python statement from hint 3
mv macros/generate_schema_name.sql.bak macros/generate_schema_name.sql
rm models/marts/_probe.sql
```

#### Validation query

```bash
python3 -c "import json; m=json.load(open('target/manifest.json')); \
print({n['name']: n['schema'] for n in m['nodes'].values() \
if n.get('config', {}).get('schema') == 'marts'})"
```

#### Validator (`src/challenges.js`)

```js
async validator(answer) {
  if (norm(answer) === "main_marts") return { ok: true,  message: "main_marts ✓ — default concatenation in action." };
  if (norm(answer) === "marts")      return { ok: false, message: "That's what the override produces. The puzzle asks for the *default* (override disabled)." };
  return { ok: false, message: "Format is <target_schema>_<custom_schema>. Target is 'main'." };
}
```

#### Why this works

dbt's default `generate_schema_name` does
`{{ target.schema }}_{{ custom_schema_name }}`. Target is `main`, custom
is `marts` → `main_marts`. The project's override macro replaces that
concatenation with just `custom_schema_name`, which is why teams
override it almost universally in production.

> **Python statement verified:** I tested the hint-3 Python snippet
> against a representative manifest fixture (probe node with
> `config.schema=marts`, `schema=main_marts`) — it prints
> `{'_probe': 'main_marts'}` as intended. Not end-to-end tested against
> a freshly built dbt project (would require materializing the probe),
> but the dbt 1.11 manifest structure is standard so the snippet should
> behave identically.

---

## Planet 6 — Tempus

### Challenge 601 — Snapshot: Freeze Frame

**Difficulty:** hard · **Points:** 60 · **Answer:** `50.0`

#### Contestant prompt

> Source systems lose history. The product catalog you have today
> overwrites prices when the merchandiser changes them — but the finance
> team needs to ask "what was SKU X priced at on date Y?". dbt's snapshot
> feature builds Slowly Changing Dimension Type 2 history for exactly
> this case.
>
> The raw_products table represents the catalog today. There's also a
> raw_products_v2 — a hypothetical "later state" with twelve price
> changes and three deactivations. Build a snapshot of the products
> catalog, run it against the current state to capture today's prices,
> then point it at the later state and run it again so the changes get
> captured as SCD2 rows. This source has no reliable `updated_at`
> column, so think about which snapshot strategy applies.
>
> **Business question:** across all the price changes captured in the
> snapshot, what's the largest percentage increase? (1 decimal place.)

#### Hints

1. Snapshots live in `snapshots/` and use a `{% snapshot name %}...{% endsnapshot %}` block. Config goes in a `{{ config(...) }}` call inside the block.
2. Two strategies: `timestamp` (uses an updated_at column) or `check` (compares specified columns). Pick based on what's available.
3. dbt adds four columns to every snapshot output: dbt_valid_from, dbt_valid_to, dbt_updated_at, dbt_scd_id. Current rows have dbt_valid_to = NULL; superseded rows have a timestamp.

#### Files changed

`models/staging/_sources.yml` *(modify — add product sources)*:

```yaml
      - name: raw_products
      - name: raw_products_v2
```

`snapshots/snap_products.sql` *(new)* — `check` strategy because no reliable `updated_at`:

```jinja
{% snapshot snap_products %}

{{ config(
    unique_key='id',
    strategy='check',
    check_cols=['base_price_cents', 'is_active']
) }}

SELECT * FROM {{ source('jaffle_shop', 'raw_products') }}

{% endsnapshot %}
```

#### Build (two passes, swapping the FROM in between)

```bash
just snapshot
# Now edit snap_products.sql: raw_products → raw_products_v2
just snapshot
```

#### Validation query

```sql
WITH old AS (
    SELECT id, base_price_cents
    FROM snapshots.snap_products
    WHERE dbt_valid_to IS NOT NULL
),

new AS (
    SELECT id, base_price_cents
    FROM snapshots.snap_products
    WHERE dbt_valid_to IS NULL
)

SELECT ROUND(MAX((n.base_price_cents - o.base_price_cents) * 100.0 / o.base_price_cents), 1)
FROM old AS o
JOIN new AS n USING (id)
WHERE o.base_price_cents != n.base_price_cents;
```

#### Validator (`src/challenges.js`)

```js
async validator(answer) {
  const g = asFloat(answer, 1);
  if (g === 50.0)      return { ok: true,  message: "50.0% ✓" };
  if (g > 0 && g < 50) return { ok: false, message: `Got ${g}%. You're missing some history — did you run the snapshot twice, against both source states?` };
  return { ok: false, message: `Got ${g}. Expected the max percentage increase across all captured price changes, 1dp.` };
}
```

#### Why this works

Product id=42 is seeded with `base_price_cents=1000` in `raw_products`
and `1500` in `raw_products_v2` — exactly a 50.0% increase, the seeded
maximum across all 12 changes.

---

### Challenge 602 — Incremental: Don't Rebuild the World

**Difficulty:** hard · **Points:** 65 · **Answer:** `42`

#### Contestant prompt

> The web events table keeps growing. Rebuilding it from scratch every
> time something downstream changes is wasteful — and at real scale,
> impossible. dbt's incremental materialization processes only what's
> new on subsequent runs.
>
> Build an incremental staging model over the web events table. On the
> initial run it loads everything; on subsequent runs it loads only
> events newer than what's already in the table. There's a separate
> "latest" version of the source containing late-arriving rows from
> 2026-01-01 to 2026-01-15 — after your initial load, swap the model to
> read from that one and re-run. Only the new rows should land.
>
> Use the event timestamp as your watermark, not the row id. IDs can be
> reused, sharded, or non-monotonic — timestamps are the safer choice.
>
> **Business question:** how many events occurred on 2026-01-15?
>
> Docs: https://docs.getdbt.com/docs/build/incremental-models

#### Hints

1. Configuration goes in a `{{ config(...) }}` call at the top of the SQL file. You'll need at least `materialized`, `unique_key`, and `incremental_strategy`.
2. The `is_incremental()` function returns true on runs where the model already exists AND `--full-refresh` wasn't passed. Use it inside a jinja `{% if %}` to gate the incremental-only WHERE clause.
3. The `{{ this }}` variable resolves to the fully-qualified name of the current model — use it to query "what's the current max timestamp in my own table?".

#### Files changed

`models/staging/_sources.yml` *(modify — add web event sources)*:

```yaml
      - name: raw_web_events
      - name: raw_web_events_latest
```

`models/staging/stg_web_events_incremental.sql` *(new)*:

```sql
{{ config(
    materialized='incremental',
    unique_key='id',
    incremental_strategy='delete+insert'
) }}

SELECT
    id,
    session_id,
    customer_id,
    event_type,
    product_id,
    utm_source,
    utm_medium,
    utm_campaign,
    CAST(event_at AS TIMESTAMP) AS event_at
FROM {{ source('jaffle_shop', 'raw_web_events') }}

{% if is_incremental() %}
WHERE CAST(event_at AS TIMESTAMP) > (SELECT MAX(event_at) FROM {{ this }})
{% endif %}
```

#### Build (two passes, swapping the FROM in between)

```bash
just run --select stg_web_events_incremental
# Now edit the FROM: raw_web_events → raw_web_events_latest
just run --select stg_web_events_incremental
```

#### Validation query

```sql
SELECT COUNT(*) FROM stg_web_events_incremental
WHERE CAST(event_at AS DATE) = '2026-01-15';
```

#### Validator (`src/challenges.js`)

```js
async validator(answer) {
  const g = asInt(answer);
  if (g === 42) return { ok: true,  message: "42 ✓" };
  if (g === 0)  return { ok: false, message: "Zero — did you swap the source to the 'latest' version and re-run?" };
  return { ok: false, message: `Got ${g}. Expected the event count on 2026-01-15.` };
}
```

#### Why this works

`raw_web_events_latest` is a superset of the base table with ~2k rows
spanning 2026-01-01 → 2026-01-15. Exactly 42 of those have `event_at`
on 2026-01-15. The `is_incremental()` guard ensures only the new rows
land on the second run.

#### Bonus

Run with `--full-refresh` and observe dbt drop and rebuild from
scratch. When is that actually the right call in production? (Schema
changes, late-arriving backfills, watermark drift.)

---

## Planet 7 — Marsius

### Challenge 701 — The Line-Item Fact

**Difficulty:** hard · **Points:** 60 · **Answer:** `P0229`

#### Contestant prompt

> Order headers are fine for payment-related questions, but most
> analytical questions live at the *line* grain — revenue by product, by
> category, the impact of discounts. The mart layer is where you build
> the workhorse facts that BI tools will actually query.
>
> Build a line-item fact that brings together order lines with their
> product and customer context. One row per line item. Denormalize the
> useful dimensions (product SKU, customer country, category name) onto
> the fact so analysts don't have to chase joins.
>
> Prerequisite: you don't have staging models yet for order items,
> products, or product categories — build small `stg_` ones first (same
> patterns as Planet 1: rename, cast, no joins), declare their sources,
> then build the fact on top of them.
>
> For revenue, use the pre-computed `line_total` column on each line
> item (already factors in quantity, unit_price, and discount).
>
> Then add a referential-integrity test that catches any line referencing
> a product that doesn't exist. The test must pass.
>
> **Business question:** which single product (by SKU) has generated the most
> revenue across all time?

#### Hints

1. You'll need new staging models for order items, products, and product categories — same patterns as Planet 1 (rename, cast).
2. The `--select` graph operator `+model_name` builds everything upstream of `model_name` in one command, in dependency order. Useful for kicking off the whole new chain.
3. The `relationships` test takes a `to:` (a `ref()` to the dimension) and a `field:` (the column on the dimension). In dbt 1.11+, use the nested `arguments:` syntax.

#### Files changed

`models/staging/_sources.yml` *(modify — add line-item sources)*:

```yaml
      - name: raw_order_items
      - name: raw_product_categories
```
(`raw_products` was already added in 601.)

`models/staging/stg_order_items.sql` *(new)*:

```sql
SELECT
    id              AS order_item_id,
    order_id,
    product_id,
    quantity,
    unit_price,
    discount_pct,
    line_total
FROM {{ source('jaffle_shop', 'raw_order_items') }}
```

`models/staging/stg_products.sql` *(new)*:

```sql
SELECT
    id                  AS product_id,
    sku                 AS product_sku,
    name                AS product_name,
    category_id         AS subcategory_id,
    base_price_cents,
    is_active
FROM {{ source('jaffle_shop', 'raw_products') }}
```

`models/staging/stg_product_categories.sql` *(new)*:

```sql
SELECT
    id                          AS category_id,
    name                        AS category_name,
    parent_category_id
FROM {{ source('jaffle_shop', 'raw_product_categories') }}
```

`models/marts/fct_order_items.sql` *(new)*:

```sql
WITH order_items AS (
    SELECT * FROM {{ ref('stg_order_items') }}
),

orders AS (
    SELECT order_id, customer_id, ordered_date FROM {{ ref('stg_orders') }}
),

customers AS (
    SELECT customer_id, country AS customer_country FROM {{ ref('stg_customers') }}
),

products AS (
    SELECT product_id, product_sku, subcategory_id FROM {{ ref('stg_products') }}
),

categories AS (
    SELECT category_id, category_name FROM {{ ref('stg_product_categories') }}
)

SELECT
    oi.order_item_id,
    oi.order_id,
    o.customer_id,
    c.customer_country,
    oi.product_id,
    p.product_sku,
    cat.category_name,
    o.ordered_date,
    oi.quantity,
    oi.unit_price,
    oi.discount_pct,
    oi.line_total
FROM order_items AS oi
INNER JOIN orders AS o      ON oi.order_id = o.order_id
INNER JOIN customers AS c   USING (customer_id)
INNER JOIN products AS p    USING (product_id)
LEFT JOIN categories AS cat ON p.subcategory_id = cat.category_id
```

`models/marts/_models.yml` *(new)*:

```yaml
version: 2

models:
  - name: fct_order_items
    description: "One row per order line. Denormalized with customer country and product/category context."
    columns:
      - name: order_item_id
        data_tests: [unique, not_null]
      - name: product_id
        data_tests:
          - relationships:
              arguments:
                to: ref('stg_products')
                field: product_id
```

#### Build

```bash
just build --select +fct_order_items
```

#### Validation query

```sql
SELECT product_sku
FROM fct_order_items
GROUP BY product_sku
ORDER BY SUM(line_total) DESC
LIMIT 1;
```

#### Validator (`src/challenges.js`)

```js
async validator(answer) {
  const a = norm(answer).toUpperCase();
  if (/^P\d{4}$/.test(a) && a === "P0229") {
    return { ok: true, message: `${a} ✓` };
  }
  if (!/^P\d{4}$/.test(a)) {
    return { ok: false, message: "Expected SKU format P#### (e.g. P0042)." };
  }
  return { ok: false, message: `${a} — right shape, wrong SKU. Sum line_total, not unit_price.` };
}
```

#### Why this works

`line_total` is pre-computed in the source (quantity × unit_price ×
(1 - discount)). Summing across all line items per SKU and ranking,
`P0229` tops the list at $11,137.46 lifetime revenue.

---

### Challenge 702 — RFM Segments

**Difficulty:** expert · **Points:** 90 · **Answer:** `2278`

#### Contestant prompt

> RFM is a classic CRM segmentation: Recency (days since last order),
> Frequency (number of orders), Monetary (lifetime spend). You bucket
> each into quintiles, concatenate the scores, and classify customers
> into segments like "champions" (high on all three) and "lost" (low on
> all three).
>
> Build an aggregate mart at customer grain. Source it from the
> line-item fact you built in 701 — that's where the analytical truth
> lives. For each customer, compute the three RFM dimensions, score
> each into 5 buckets via window functions, then apply the segmentation
> rules below in this exact order (first match wins):
>
>     r>=4 AND f>=4 AND m>=4  → champions
>     r>=4 AND f<=2           → new_customers
>     r>=3 AND f>=3           → loyal
>     r<=2 AND m>=3           → at_risk
>     r<=2 AND f<=2           → lost
>     otherwise               → other
>
> Specifications you need to follow so the puzzle answer is deterministic:
>
> > - As-of date for recency:  `DATE '2026-01-01'` (hardcoded)
> > - Recency direction:       lower recency_days → higher r_score.
> >                            `NTILE(5) OVER (ORDER BY recency_days DESC, customer_id)`
> >                            — the customer_id tiebreaker prevents
> >                            non-determinism on ties.
> > - Frequency:               `COUNT(DISTINCT order_id)` from the fact.
> >                            `NTILE(5) OVER (ORDER BY frequency ASC, customer_id)`.
> > - Monetary:                `SUM(line_total)` from the fact (already
> >                            discount-adjusted; ignores order status).
> >                            `NTILE(5) OVER (ORDER BY monetary ASC, customer_id)`.
>
> Add uniqueness and not-null tests on the customer key — both must pass.
>
> **Business question:** how many customers fall into the 'champions' segment?

#### Hints

1. The bucketing function is `NTILE(5) OVER (ORDER BY ...)`. ORDER BY direction decides which end is "best": for recency, the most recent date should be score 5.
2. For the unique-customer test to pass, your aggregation has to be at customer grain — no accidental fan-out from joining the per-line fact without aggregating first.
3. The CASE branches must be in order — the first matching rule wins. A "champion" also satisfies "loyal", so champions has to come first.

#### Files changed

`models/marts/agg_customer_rfm.sql` *(new)*:

```sql
WITH fct AS (
    SELECT * FROM {{ ref('fct_order_items') }}
),

per_customer AS (
    SELECT
        customer_id,
        (DATE '2026-01-01' - MAX(ordered_date))::INTEGER  AS recency_days,
        COUNT(DISTINCT order_id)                          AS frequency,
        SUM(line_total)                                   AS monetary
    FROM fct
    GROUP BY customer_id
),

scored AS (
    SELECT
        customer_id,
        recency_days,
        frequency,
        monetary,
        NTILE(5) OVER (ORDER BY recency_days DESC, customer_id) AS r_score,
        NTILE(5) OVER (ORDER BY frequency ASC, customer_id)     AS f_score,
        NTILE(5) OVER (ORDER BY monetary ASC, customer_id)      AS m_score
    FROM per_customer
)

SELECT
    customer_id,
    recency_days,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    CASE
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'champions'
        WHEN r_score >= 4 AND f_score <= 2                  THEN 'new_customers'
        WHEN r_score >= 3 AND f_score >= 3                  THEN 'loyal'
        WHEN r_score <= 2 AND m_score >= 3                  THEN 'at_risk'
        WHEN r_score <= 2 AND f_score <= 2                  THEN 'lost'
        ELSE 'other'
    END AS segment
FROM scored
```

`models/marts/_models.yml` *(modify — add unique/not_null on customer_id)*:

```yaml
  - name: agg_customer_rfm
    description: "Per-customer RFM scores and segment classification, as-of 2026-01-01."
    columns:
      - name: customer_id
        data_tests: [unique, not_null]
```

#### Build

```bash
just build --select agg_customer_rfm
```

#### Validation query

```sql
SELECT COUNT(*) FROM agg_customer_rfm WHERE segment = 'champions';
```

#### Validator (`src/challenges.js`)

```js
async validator(answer) {
  const g = asInt(answer);
  if (g === 2278) return { ok: true,  message: `${g} ✓` };
  return { ok: false, message: `Got ${g}. Expected the count of customers whose r, f, AND m scores are all >= 4.` };
}
```

#### Why this works

The customer_id tiebreaker in every NTILE makes scoring deterministic.
2,278 customers land in the top quintile on all three dimensions.

---

### Challenge 703 — The Marketing Funnel

**Difficulty:** expert · **Points:** 90 · **Answer:** `instagram`

#### Contestant prompt

> The marketing team's first question is always "which channel converts?".
> Without a canonical funnel mart, every analyst writes their own version
> and gets different numbers — and the team stops trusting the data.
>
> Build a funnel mart at utm_source grain on top of the incremental web
> events model from the previous planet (this is the payoff — that
> incremental model finally gets consumed). Per channel, count distinct
> sessions (one row per `session_id`) at each of these stages:
>
> > - viewed         a `page_view` event WHERE product_id IS NOT NULL
> > - added_to_cart  an `add_to_cart` event
> > - checked_out    a `checkout_start` event
> > - purchased      a `purchase` event
>
> Compute a cart-to-purchase conversion percentage rounded to 1 decimal
> place. Bucket NULL utm_source as '(none)'.
>
> Add not-null tests on the channel name and session count.
>
> **Business question:** which utm_source has the highest cart-to-purchase
> percentage? (Ignore '(none)'.)

#### Hints

1. Per-session attribution typically picks the FIRST utm_source seen in the session. The SQL pattern is `FIRST_VALUE(...) OVER (PARTITION BY session_id ORDER BY event_at)`.
2. Per-session funnel flags are conditional aggregations: `MAX(CASE WHEN event_type = '...' THEN 1 ELSE 0 END)` collapses many events to one boolean per session.
3. Use `NULLIF(carted, 0)` in the divisor to avoid divide-by-zero for channels with no carts.

#### Files changed

`models/marts/fct_funnel_by_channel.sql` *(new)*:

```sql
WITH events AS (
    SELECT * FROM {{ ref('stg_web_events_incremental') }}
),

session_attr AS (
    SELECT DISTINCT
        session_id,
        FIRST_VALUE(utm_source) OVER (
            PARTITION BY session_id ORDER BY event_at
        ) AS utm_source
    FROM events
),

session_flags AS (
    SELECT
        session_id,
        MAX(CASE WHEN event_type = 'page_view' AND product_id IS NOT NULL
                 THEN 1 ELSE 0 END) AS has_view,
        MAX(CASE WHEN event_type = 'add_to_cart'    THEN 1 ELSE 0 END) AS has_cart,
        MAX(CASE WHEN event_type = 'checkout_start' THEN 1 ELSE 0 END) AS has_checkout,
        MAX(CASE WHEN event_type = 'purchase'       THEN 1 ELSE 0 END) AS has_purchase
    FROM events
    GROUP BY session_id
)

SELECT
    COALESCE(sa.utm_source, '(none)')   AS utm_source,
    COUNT(*)                            AS sessions,
    SUM(sf.has_view)                    AS viewed,
    SUM(sf.has_cart)                    AS carted,
    SUM(sf.has_checkout)                AS checked_out,
    SUM(sf.has_purchase)                AS purchased,
    ROUND(SUM(sf.has_purchase) * 100.0 / NULLIF(SUM(sf.has_cart), 0), 1)
        AS cart_to_purchase_pct
FROM session_flags AS sf
JOIN session_attr  AS sa USING (session_id)
GROUP BY 1
```

`models/marts/_models.yml` *(modify — add not_null tests)*:

```yaml
  - name: fct_funnel_by_channel
    description: "Per utm_source funnel counts and cart-to-purchase conversion."
    columns:
      - name: utm_source
        data_tests: [not_null]
      - name: sessions
        data_tests: [not_null]
```

#### Build

```bash
just build --select fct_funnel_by_channel
```

#### Validation query

```sql
SELECT utm_source
FROM fct_funnel_by_channel
WHERE utm_source != '(none)'
ORDER BY cart_to_purchase_pct DESC NULLS LAST
LIMIT 1;
```

#### Validator (`src/challenges.js`)

```js
async validator(answer) {
  const accepted = new Set(["google","facebook","instagram","tiktok","newsletter","direct","organic"]);
  const a = norm(answer);
  if (a === "instagram") return { ok: true,  message: `${a} ✓` };
  if (accepted.has(a))   return { ok: false, message: `${a} — real source but not the leader. Re-check the ORDER BY.` };
  return { ok: false, message: "Expected one of the seven UTM sources in the data, all lowercase." };
}
```

#### Why this works

Cart-to-purchase rates by channel (verified against starter.duckdb on
2026-05-25):

| utm_source  | pct  |
|-------------|------|
| instagram   | 17.6 |
| tiktok      | 17.4 |
| facebook    | 17.2 |
| newsletter  | 16.9 |
| google      | 16.9 |
| organic     | 16.7 |
| direct      | 16.4 |

Instagram leads by 0.2pp over tiktok — small but well above any
rounding ambiguity.

---

## Cross-cutting answer table

| ID  | Title                          | Difficulty | Points | Answer            |
|-----|--------------------------------|------------|--------|-------------------|
| 101 | First Light                    | easy       | 15     | `42`              |
| 102 | Know Your Sources              | easy       | 20     | `2`               |
| 103 | The Seed Vault                 | easy       | 20     | `3193396.14`      |
| 201 | Chain Reaction                 | medium     | 30     | `8584`            |
| 202 | Trust, but Verify              | medium     | 35     | `3`               |
| 203 | The Full Build                 | medium     | 35     | `3`               |
| 301 | Selective Operations           | medium     | 30     | `1`               |
| 302 | Custom Tests                   | hard       | 55     | `1`               |
| 401 | Documentation Station          | medium     | 30     | `4`               |
| 402 | The Macro Workshop             | hard       | 60     | `d4dfe0d3`        |
| 501 | Materializations & Ghosts      | medium     | 30     | `4`               |
| 502 | Schema Mastery                 | hard       | 50     | `main_marts`      |
| 601 | Snapshot: Freeze Frame         | hard       | 60     | `50.0`            |
| 602 | Incremental                    | hard       | 65     | `42`              |
| 701 | The Line-Item Fact             | hard       | 60     | `P0229`           |
| 702 | RFM Segments                   | expert     | 90     | `2278`            |
| 703 | The Marketing Funnel           | expert     | 90     | `instagram`       |

Total mission credits: **775**.

## Notes for the maintainer

**Answer collisions:** 202 and 203 both answer `3` by design (202 finds
the broken rows, 203 verifies the cleanup dropped those exact rows).
Don't change one validator without updating the other.

**Contestant-dependent counts:** 401's answer (`4`) depends on
contestants documenting every model in scope. The validator gives
diagnostic feedback for partial counts (`X/4`) but only `4` passes —
this is a discipline lesson.

**Re-verification protocol:** after any change to
`scripts/generate_starter_db.py` (or `starter.duckdb`), re-run every
validation query in this document against the new starter DB. Update
both this file AND the `__ANS__` placeholders in
`voyager_challenges.md` in lockstep. The selector-based answers (102,
301) and structural answers (401, 502) don't depend on seed values and
should remain stable as long as the challenge spec doesn't change.
