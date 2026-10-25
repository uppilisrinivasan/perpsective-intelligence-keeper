---
id: calibration_notes
version: 1
role: deep
temperature: 0.2
top_p: 1
reasoning: "off"
max_output_tokens: 400
output_schema: calibration_notes
allow_fallback: true
cache: true
---
{# system #}
Explain one lens item's track record in two plain sentences, using only the numbers and outcome titles given.
Do not change or judge the status. {% include "_voice.md" %}
Return JSON only, matching the schema.
{# user #}
Item: {{ item.title }} ({{ item.type }}, status {{ item.status }})
Numbers: ignored {{ numbers.n_ignored }}, bad outcomes after ignoring {{ numbers.k_bad }}, hit rate {{ numbers.hit_rate }},
90% interval {{ numbers.ci90 }}, base rate {{ numbers.base_rate }}, support {{ numbers.support }}.
Outcomes: {% for t in outcome_titles %}{{ t | untrusted }}; {% endfor %}
