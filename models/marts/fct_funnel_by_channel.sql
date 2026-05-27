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
