SELECT
    id                  AS product_id,
    sku                 AS product_sku,
    name                AS product_name,
    category_id         AS subcategory_id,
    base_price_cents,
    is_active
FROM {{ source('jaffle_shop', 'raw_products') }}
