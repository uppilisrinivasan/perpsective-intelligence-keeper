# The assistant ("Ask")

The assistant is the plain-language way into everything Keeper knows: a prompt-and-response chat like ChatGPT or Claude. It reads Keeper's data through tools, answers with citations, and proposes actions as confirmation cards. It does not replace the screens; it links into them.

## 1. Loop

```
POST /api/v1/chat/threads/{tid}/messages {text, context?}   → SSE
1. persist user message; load thread (last N turns within assistant.history_tokens, older turns summarised once by fast model)
2. build system prompt (config/prompts/assistant_system.md): who Keeper is, the four lanes, the rules
   (answer only from tool results; cite; never claim to have merged/posted; costs need confirmation), current
   project, viewer role, demo_now, live/saved mode, attached context (e.g. "user is viewing PR #412")
3. call assistant role with tools (stream)
4. on tool calls: validate args (JSON Schema) → run tool via keeper.services (same permission checks as the API)
   → emit chat.tool_step {name, label, status} → append tool result (truncated to assistant.tool_result_tokens) → continue
5. max assistant.max_tool_rounds (6) rounds; then answer with what it has
6. stream final text (chat.delta); emit chat.card for each citation/action; persist assistant message with cards + tool trace
7. chat.done {usage, cost_usd}
```

If the model does not support tools (probe), a **router fallback** is used: the fast model classifies the intent into one of the tools with arguments (JSON schema), Keeper runs it, and the assistant role writes the answer from the result. This is one round.

## 2. Tools

Read-only tools run freely. Action tools never run directly: they return a **proposal**, which the UI renders as a confirmation card. The action happens only when the user clicks **Confirm**, which calls the normal API endpoint.

| Tool | Kind | Arguments | Returns |
|---|---|---|---|
| `get_queue` | read | `lane?`, `limit?` | Rows: number, title, lane, reasons, attention |
| `get_pull` | read | `number` | Summary, lane, findings by lane (titles, anchors), signals, fix status |
| `get_finding` | read | `finding_id` | Full finding with evidence and lens items |
| `search_history` | read | `query`, `author?`, `path?`, `since?` | Matching past review comments (BM25 over `review_comments`), with links |
| `get_lens` | read | `person?`, `version?` | Lens card summary, items (top N), health |
| `get_lens_item` | read | `item_id` | The item with exemplars |
| `diff_lens_versions` | read | `from`, `to` | Added, removed and changed items |
| `get_proof` | read | `run_id?` | Latest fidelity metrics and falsifier results |
| `get_growth` | read | `person` | Growth residual G, health state, history |
| `get_usage` | read | `period?` | Spend by model and feature |
| `explain_concept` | read | `term` | The glossary entry from `config/glossary.yaml` (the same source as the UI's tooltips) |
| `propose_analyze` | action | `number` | A card: "Analyse PR #N again · ≈ $0.02" |
| `propose_fix` | action | `number`, `finding_ids` | A card with the estimate |
| `propose_handoff` | action | `number` | A card: the suggested reviewer and why |
| `propose_rebuild_lens` | action | `reason` | A card with the estimate |
| `propose_fidelity_run` | action | — | A card with the estimate (and a batch option) |
| `propose_practice` | action | `person?`, `length?` | A card: start a practice session |

Tools are defined once in `keeper.assistant.tools` with pydantic argument models; their JSON Schemas are generated for the model. Every tool call is recorded in the message's `tool_trace` (name, arguments, duration, truncated result size), visible in the collapsible step lines.

## 3. Cards

| Card type | Fields | UI |
|---|---|---|
| `pull` | number, title, lane, one-line reason | A clickable chip → the PR view |
| `finding` | id, title, lane colour, anchor | Chip → the PR view scrolled to the finding |
| `comment` | id, author, date, excerpt, PR | Quote block with a link |
| `lens_item` | id, title, kind, support | Chip → Lens, with the item open |
| `metric` | name, value, interval, pass | Inline stat |
| `action` | action kind, label, estimate, params, `expires_at` | A confirmation card with **Confirm** and **Cancel**; disabled in no-key mode |

The model cites using markers `[[pull:412]]`, `[[finding:f_…]]` and so on. The server resolves them to cards, and **drops markers that do not refer to an object returned by a tool in this turn** (an anti-hallucination check). Dropped markers are logged.

## 4. Suggested prompts

They come from `GET /api/v1/chat/suggestions?context=…`. They are built from data, not hardcoded:
- Queue: "Why does #{top_unknown} need another reviewer?", "What's handled for me this week?"
- PR: "What would {maintainer} notice here?", "Show me past comments like finding {top_edge}."
- Lens: "What changed in my lens since v{prev}?", "What does my lens miss?"
- Proof: "Explain the result in one paragraph."
- Practice: "What should I practise next?"

The templates live in `config/ui.yaml` (`assistant.suggestions`); slot values come from the current data.

## 5. Context drawer ("Ask about this")

On Queue, PR, Lens, Proof and Practice, a button opens Ask as a right-side drawer (a full-screen sheet below the `md` container width) with the context attached as a chip ("PR #412" ×). The drawer and the Ask page share the thread model. A drawer conversation appears in the thread list under its context.

## 6. Without a key

Ask shows: "Ask needs a Nemotron API key. Here are saved answers to common questions." It lists `data/snapshots/<project>/chat_examples.jsonl`, saved question-and-answer pairs (with cards) produced by the snapshot job using real tool calls. They are rendered as read-only threads labelled "Saved".

## 7. Safety

- The system prompt and the tool results are separated, and tool results are wrapped as data (`<tool_result>…</tool_result>`), with an instruction that content inside is untrusted.
- PR and comment text in tool results is redacted (gateway redaction) and truncated.
- The assistant cannot call GitHub, run shell commands, or reach any endpoint not listed above.
