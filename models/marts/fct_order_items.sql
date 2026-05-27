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
