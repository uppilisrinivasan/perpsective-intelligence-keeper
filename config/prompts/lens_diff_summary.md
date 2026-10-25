---
id: lens_diff_summary
version: 1
role: judge
temperature: 0.2
top_p: 1
reasoning: "off"
max_output_tokens: 500
output_schema: lens_diff_summary
allow_fallback: true
cache: true
---
{# system #}
Summarise what changed between two versions of a reviewer's lens in exactly three short bullets, from the computed
diff only. Add no changes that are not in it. {% include "_voice.md" %}
Return JSON only, matching the schema.
{# user #}
{% for c in changes %}- {{ c.change }}: {{ c.title }}{% if c.detail %} ({{ c.detail }}){% endif %}
{% endfor %}
