{% macro generate_surrogate_key(field_list) %}
    MD5(
        {%- for f in field_list %}
        COALESCE(CAST({{ f }} AS VARCHAR), '_null_')
        {%- if not loop.last %} || '|' || {%- endif %}
        {%- endfor %}
    )
{% endmacro %}
