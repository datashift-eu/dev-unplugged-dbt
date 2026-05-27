SELECT
    id                          AS category_id,
    name                        AS category_name,
    parent_category_id
FROM {{ source('jaffle_shop', 'raw_product_categories') }}
