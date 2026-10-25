import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Card } from "@/api/types";
import { Markdown } from "@/components/ui/Markdown";
import { cardId, findMarkers, indexCards, parseCiteHref, prepareMarkers } from "@/lib/markers";

const cards: Card[] = [
  { type: "pull", data: { number: 7, title: "A change", lane: "edge" } },
  { type: "lens_item", data: { id: "li_x", title: "A pattern" } },
];

describe("citation markers", () => {
  it("finds markers with type and id", () => {
    expect(findMarkers("See [[pull:7]] and [[lens_item:li_x]].").map((m) => [m.type, m.id])).toEqual([
      ["pull", "7"],
      ["lens_item", "li_x"],
    ]);
  });

  it("resolves card ids from data.id or data.number", () => {
    expect(cards.map(cardId)).toEqual(["7", "li_x"]);
  });

  it("keeps placeholders while streaming and hides a partial marker", () => {
    const idx = indexCards([]);
    const s = prepareMarkers("Look at [[pull:7]] and [[lens_it", idx, false);
    expect(s).toContain("#keeper-cite/pull/7");
    expect(s).not.toContain("[[lens_it");
  });

  it("drops unresolved markers when done", () => {
    const idx = indexCards(cards);
    const s = prepareMarkers("A [[pull:7]] B [[finding:f_missing]] C", idx, true);
    expect(s).toContain("#keeper-cite/pull/7");
    expect(s).not.toContain("f_missing");
    expect(s).not.toContain("[[");
  });

  it("parses citation hrefs", () => {
    expect(parseCiteHref("#keeper-cite/lens_item/li_x")).toEqual({ type: "lens_item", id: "li_x" });
    expect(parseCiteHref("https://example.org")).toBeNull();
  });

  it("renders a chip through the sanitised markdown renderer", () => {
    const text = prepareMarkers("Because of [[pull:7]].", indexCards(cards), true);
    render(<Markdown source={text} renderCitation={(type, id) => <span data-testid="chip">{`${type}-${id}`}</span>} />);
    expect(screen.getByTestId("chip").textContent).toBe("pull-7");
  });
});
