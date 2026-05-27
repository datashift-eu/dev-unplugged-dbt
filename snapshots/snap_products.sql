{% snapshot snap_products %}

{{ config(
    unique_key='id',
    strategy='check',
    check_cols=['base_price_cents', 'is_active']
) }}

SELECT * FROM {{ source('jaffle_shop', 'raw_products_v2') }}

{% endsnapshot %}
