"use client";

import { useEffect, useRef, useState } from "react";
import { Markdown } from "@/components/Markdown";
import { safeMarkdownPrefix } from "@/lib/streamingMarkdown";

const TICK_MS = process.env.NODE_ENV === "test" ? 1 : 12;
const CHARS_PER_TICK = 3;

// Client-side text reveal after the validated `message` event (no token deltas on wire).
// Renders markdown on each visible prefix so bold/lists never show raw asterisks mid-stream.
export function StreamingText({
  text,
  active,
  onComplete,
}: {
  text: string;
  active: boolean;
  onComplete: () => void;
}) {
  const [visibleLen, setVisibleLen] = useState(0);
  const completedRef = useRef(false);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  useEffect(() => {
    if (!active) {
      setVisibleLen(text.length);
      return;
    }
    setVisibleLen(0);
    completedRef.current = false;
    let i = 0;
    const id = window.setInterval(() => {
      i = Math.min(i + CHARS_PER_TICK, text.length);
      setVisibleLen(i);
      if (i >= text.length) {
        window.clearInterval(id);
        if (!completedRef.current) {
          completedRef.current = true;
          onCompleteRef.current();
        }
      }
    }, TICK_MS);
    return () => window.clearInterval(id);
  }, [text, active]);

  const showCursor = active && visibleLen < text.length;
  const visible = safeMarkdownPrefix(text, visibleLen);

  return (
    <div
      className="bubble bubble--assistant md streaming-text"
      data-testid="streaming-text"
    >
      {visible.length > 0 && <Markdown>{visible}</Markdown>}
      {showCursor && <span className="streaming-cursor" aria-hidden="true" />}
    </div>
  );
}
