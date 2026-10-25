/**
 * Citation markers in assistant text, e.g. [[pull:412]] or [[lens_item:li_x]] (docs/04-architecture/06-assistant.md §3).
 * The server resolves them to cards; the client renders each as a chip, shows a placeholder until its card
 * arrives, and drops unresolved markers when the answer is done.
 */
import type { Card } from "@/api/types";
import { obj, str } from "./unknown";

export const MARKER_RE = /\[\[([a-z_]+):([^\]\s]+?)\]\]/g;
export const CITE_PREFIX = "#keeper-cite/";

export interface Marker {
  type: string;
  id: string;
  raw: string;
  index: number;
}

export function findMarkers(text: string): Marker[] {
  const out: Marker[] = [];
  for (const m of text.matchAll(MARKER_RE)) {
    out.push({ type: m[1] ?? "", id: m[2] ?? "", raw: m[0], index: m.index ?? 0 });
  }
  return out;
}

/** The id a card answers to: data.id, or data.number for pulls, or data.name for metrics. */
export function cardId(card: Card): string | undefined {
  const d = obj(card.data);
  return str(d.id) ?? str(d.number) ?? str(d.pr_number) ?? str(d.key) ?? str(d.name);
}

export function cardKey(type: string, id: string): string {
  return `${type}:${id}`;
}

export function indexCards(cards: Card[]): Map<string, Card> {
  const m = new Map<string, Card>();
  for (const c of cards) {
    const id = cardId(c);
    if (id !== undefined) m.set(cardKey(c.type, id), c);
  }
  return m;
}

/**
 * Rewrites markers into markdown links the Markdown renderer turns into chips.
 * While streaming, an incomplete trailing marker ("[[pul") is hidden; when `done`, unresolved markers are removed.
 */
export function prepareMarkers(text: string, cards: Map<string, Card>, done: boolean): string {
  let s = text;
  if (!done) s = s.replace(/\[\[[^\]]*$/, "").replace(/\[\[[^\]]*\]$/, "");
  return s.replace(MARKER_RE, (_raw, type: string, id: string) => {
    const known = cards.has(cardKey(type, id));
    if (!known && done) return "";
    return `[⁠](${CITE_PREFIX}${encodeURIComponent(type)}/${encodeURIComponent(id)})`;
  }).replace(/ {2,}/g, " ");
}

export function parseCiteHref(href: string | undefined): { type: string; id: string } | null {
  if (!href || !href.startsWith(CITE_PREFIX)) return null;
  const [type, id] = href.slice(CITE_PREFIX.length).split("/");
  if (!type || !id) return null;
  return { type: decodeURIComponent(type), id: decodeURIComponent(id) };
}
