import type { SseEvent } from "@/lib/types";

// Parse an SSE byte stream into typed events. The gateway frames each event as
//   event: <name>\n data: <json>\n\n
// (see gateway/chat.py). We fold the `event:` name into the JSON payload as
// `type` so the UI can switch on a single discriminant. Frames are split on the
// blank-line boundary; a trailing partial frame is buffered across chunks.
export async function* parseSse(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<SseEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const event = parseFrame(frame);
        if (event) yield event;
        boundary = buffer.indexOf("\n\n");
      }
    }
    const tail = parseFrame(buffer);
    if (tail) yield tail;
  } finally {
    reader.releaseLock();
  }
}

function parseFrame(frame: string): SseEvent | null {
  let name = "";
  const data: string[] = [];
  for (const raw of frame.split("\n")) {
    const line = raw.replace(/\r$/, "");
    if (line.startsWith(":") || line === "") continue;
    if (line.startsWith("event:")) {
      name = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      data.push(line.slice("data:".length).replace(/^ /, ""));
    }
  }
  if (!name || data.length === 0) return null;
  try {
    const payload = JSON.parse(data.join("\n"));
    return { type: name, ...payload } as SseEvent;
  } catch {
    return null;
  }
}
