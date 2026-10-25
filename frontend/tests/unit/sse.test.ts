import { describe, expect, it } from "vitest";
import { createSseParser, parseData, readSseStream, type SseMessage } from "@/api/sse";

function parseAll(chunks: string[]): SseMessage[] {
  const out: SseMessage[] = [];
  const p = createSseParser((m) => out.push(m));
  for (const c of chunks) p.feed(c);
  p.end();
  return out;
}

describe("SSE parser", () => {
  const wire = 'id: 1042\nevent: fix.test.result\ndata: {"job_id":"job_1","branch":"A","passed":118,"failed":1}\n\n: heartbeat\n\nevent: chat.delta\ndata: {"text":"hi"}\n\n';

  it("parses events, ids and JSON data", () => {
    const out = parseAll([wire]);
    expect(out).toHaveLength(2);
    expect(out[0]).toMatchObject({ event: "fix.test.result", id: "1042" });
    expect(parseData(out[0]!)).toMatchObject({ branch: "A", passed: 118 });
    expect(out[1]!.event).toBe("chat.delta");
  });

  it("is independent of chunk boundaries", () => {
    const whole = parseAll([wire]);
    for (let size = 1; size < 12; size++) {
      const chunks: string[] = [];
      for (let i = 0; i < wire.length; i += size) chunks.push(wire.slice(i, i + size));
      expect(parseAll(chunks)).toEqual(whole);
    }
  });

  it("handles CRLF, lone CR, multi-line data and a BOM", () => {
    const out = parseAll(["﻿event: a\r\ndata: one\r\ndata: two\r\n\r", "\nevent: b\rdata: x\r\r"]);
    expect(out).toEqual([
      { event: "a", data: "one\ntwo" },
      { event: "b", data: "x" },
    ]);
  });

  it("defaults the event name, ignores comments and drops an unterminated event", () => {
    const out = parseAll([": c\ndata: plain\n\ndata: dangling"]);
    expect(out).toEqual([{ event: "message", data: "plain" }]);
  });

  it("reads retry and ignores ids with NUL", () => {
    const out = parseAll(["retry: 3000\nid: a\u0000b\ndata: z\n\n"]);
    expect(out[0]).toEqual({ event: "message", data: "z", retry: 3000 });
  });

  it("reads a fetch body stream", async () => {
    const enc = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(enc.encode("event: chat.delta\ndata: {\"text\":\"Hel"));
        c.enqueue(enc.encode("lo\"}\n\nevent: chat.done\ndata: {}\n\n"));
        c.close();
      },
    });
    const out: SseMessage[] = [];
    await readSseStream(body, (m) => out.push(m));
    expect(out.map((m) => m.event)).toEqual(["chat.delta", "chat.done"]);
    expect(parseData<{ text: string }>(out[0]!)?.text).toBe("Hello");
  });

  it("returns null for non-JSON data", () => {
    expect(parseData({ data: "not json" })).toBeNull();
  });
});
