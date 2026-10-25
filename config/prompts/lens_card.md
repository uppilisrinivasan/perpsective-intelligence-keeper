---
id: lens_card
version: 1
role: judge
temperature: 0.2
top_p: 1
reasoning: "off"
max_output_tokens: 2000
output_schema: lens_card
allow_fallback: true
cache: true
---
{# system #}
Write a short, plain-language lens card for {{ person.display_name }}: what they notice in code review, in the second
person ("You notice…"). A three-sentence summary, then sections. Every bullet must cite the item IDs it is based on.
Use only the items given. Sections, in order: "What you notice" (validated edge items), "Still learning"
(candidates), "Blind spots worth knowing", "Where generic review is enough"{% if include_bias %}, "Possible bias"{% endif %}.
{% include "_voice.md" %}
Return JSON only, matching the schema.
{# user #}
{% for i in items %}- {{ i.id }} [{{ i.type }}, {{ i.status }}, {{ i.category }}, support {{ i.support }}]: {{ i.title }}. {{ i.statement }}
{% endfor %}
