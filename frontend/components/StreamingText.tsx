"use client";

import { useEffect, useRef, useState } from "react";

const CHAR_MS = process.env.NODE_ENV === "test" ? 1 : 28;

// Client-side text reveal after the validated `message` event (no token deltas on wire).
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
      i += 1;
      setVisibleLen(i);
      if (i >= text.length) {
        window.clearInterval(id);
        if (!completedRef.current) {
          completedRef.current = true;
          onCompleteRef.current();
        }
      }
    }, CHAR_MS);
    return () => window.clearInterval(id);
  }, [text, active]);

  const slice = text.slice(0, visibleLen);
  const showCursor = active && visibleLen < text.length;

  return (
    <div className="streaming-text" data-testid="streaming-text">
      {slice}
      {showCursor && <span className="streaming-cursor" aria-hidden="true" />}
    </div>
  );
}
