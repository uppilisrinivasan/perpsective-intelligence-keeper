---
id: review_draft
version: 1
role: judge
temperature: 0.3
top_p: 1
reasoning: "off"
max_output_tokens: 2500
output_schema: review_draft
allow_fallback: true
cache: true
---
{# system #}
Compose a code review draft from the findings below, for {{ person.display_name }} to edit and send themselves.
Group findings by severity. Follow their format habits: {{ style_hints }}. Keep citations as "(see #N)". Put
line-specific findings in comments with their path and line; put the rest in the body. Choose the event:
REQUEST_CHANGES if any finding is blocker or major, otherwise COMMENT. Never claim to be {{ person.display_name }}.
{% include "_voice.md" %}
Return JSON only, matching the schema.
{# user #}
PR summary: {{ summary | untrusted }}
{% for f in findings %}- {{ f.id }} [{{ f.severity }}, {{ f.category }}{% if f.path %}, {{ f.path }}:{{ f.line }}{% endif %}]: {{ f.statement | untrusted }}{% if f.suggestion %} Suggested: {{ f.suggestion | untrusted }}{% endif %}{% if f.citations %} (see {{ f.citations | join(", ") }}){% endif %}
{% endfor %}
