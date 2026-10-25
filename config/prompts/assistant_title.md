---
id: assistant_title
version: 1
role: fast
temperature: 0.2
top_p: 1
reasoning: "off"
max_output_tokens: 60
output_schema: assistant_title
allow_fallback: true
cache: true
---
{# system #}
Write a title of at most six words for a chat that starts with the message below. Return JSON only, matching the schema.
{# user #}
{{ text | untrusted }}
