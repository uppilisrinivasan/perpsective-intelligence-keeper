/**
 * Server-sent events parser shared by job streams (tests, fallbacks) and chat answers
 * (fetch + ReadableStream, because chat is a POST). Implements the WHATWG event-stream format:
 * fields `event`, `data` (multi-line joined with "\n"), `id`, `retry`; comments start with ":".
 */
export interface SseMessage {
  event: string;
  data: string;
  id?: string;
  retry?: number;
}

export interface SseParser {
  feed(chunk: string): void;
  end(): void;
}

export function createSseParser(onMessage: (m: SseMessage) => void): SseParser {
  let buffer = "";
  let event = "";
  let data: string[] = [];
  let id: string | undefined;
  let retry: number | undefined;
  let first = true;

  const dispatch = () => {
    if (data.length === 0) {
      event = "";
      return;
    }
    const m: SseMessage = { event: event || "message", data: data.join("\n") };
    if (id !== undefined) m.id = id;
    if (retry !== undefined) m.retry = retry;
    event = "";
    data = [];
    retry = undefined;
    onMessage(m);
  };

  const line = (raw: string) => {
    if (raw === "") {
      dispatch();
      return;
    }
    if (raw.startsWith(":")) return;
    const idx = raw.indexOf(":");
    const field = idx === -1 ? raw : raw.slice(0, idx);
    let value = idx === -1 ? "" : raw.slice(idx + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    switch (field) {
      case "event":
        event = value;
        break;
      case "data":
        data.push(value);
        break;
      case "id":
        if (!value.includes("\0")) id = value;
        break;
      case "retry":
        if (/^\d+$/.test(value)) retry = Number(value);
        break;
      default:
        break;
    }
  };

  return {
    feed(chunk: string) {
      if (first) {
        if (chunk.charCodeAt(0) === 0xfeff) chunk = chunk.slice(1);
        if (chunk.length > 0) first = false;
      }
      buffer += chunk;
      for (;;) {
        const match = /\r\n|\r|\n/.exec(buffer);
        if (!match) break;
        // A trailing lone "\r" may be the first half of "\r\n": wait for more input.
        if (match[0] === "\r" && match.index === buffer.length - 1) break;
        line(buffer.slice(0, match.index));
        buffer = buffer.slice(match.index + match[0].length);
      }
    },
    end() {
      if (buffer.length > 0) {
        line(buffer.replace(/\r$/, ""));
        buffer = "";
      }
      // An unterminated final event is dropped, as browsers do.
      data = [];
      event = "";
    },
  };
}

/** Reads a fetch body as an event stream until it ends or the signal aborts. */
export async function readSseStream(
  body: ReadableStream<Uint8Array>,
  onMessage: (m: SseMessage) => void,
  signal?: AbortSignal,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  const parser = createSseParser(onMessage);
  const onAbort = () => {
    reader.cancel().catch(() => undefined);
  };
  signal?.addEventListener("abort", onAbort);
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      parser.feed(decoder.decode(value, { stream: true }));
    }
    parser.feed(decoder.decode());
    parser.end();
  } finally {
    signal?.removeEventListener("abort", onAbort);
    reader.releaseLock();
  }
}

/** Parses the JSON payload of an event; returns null when it is not JSON. */
export function parseData<T = Record<string, unknown>>(m: Pick<SseMessage, "data">): T | null {
  try {
    return JSON.parse(m.data) as T;
  } catch {
    return null;
  }
}
