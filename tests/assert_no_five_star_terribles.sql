SELECT
    id,
    rating,
    review_text
FROM {{ source('jaffle_shop', 'raw_reviews') }}
WHERE rating = 5
  AND LOWER(review_text) LIKE '%terrible%'
