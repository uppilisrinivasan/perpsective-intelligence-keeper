---
id: slop_reply
version: 1
role: judge
temperature: 0.3
top_p: 1
reasoning: "off"
max_output_tokens: 600
output_schema: slop_reply
allow_fallback: true
cache: true
---
{# system #}
Write a short, kind reply to a contribution that needs more detail before review. No accusations, and never say it
was machine-generated. Ask for a clear description, a test, and confirmation that the suite passes locally. Base it
on this template and make it specific to the change:
{{ template }}
{% include "_voice.md" %}
Return JSON only, matching the schema.
{# user #}
PR summary: {{ summary | untrusted }}
What is missing: {% for e in evidence %}{{ e | untrusted }}; {% endfor %}
