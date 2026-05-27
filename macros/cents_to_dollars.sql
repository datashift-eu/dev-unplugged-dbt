{% macro cents_to_dollars(column_name) %}
    ROUND(CAST({{ column_name }} AS DECIMAL) / 100.0, 2)
{% endmacro %}
