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
