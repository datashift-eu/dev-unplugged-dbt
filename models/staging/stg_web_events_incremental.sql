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
FROM {{ source('jaffle_shop', 'raw_web_events_latest') }}

{% if is_incremental() %}
WHERE CAST(event_at AS TIMESTAMP) > (SELECT MAX(event_at) FROM {{ this }})
{% endif %}
