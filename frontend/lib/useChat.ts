"use client";

import { useCallback, useRef, useState } from "react";
import { parseSse } from "@/lib/sse";
import type { AssistantMessage, ChatMessage } from "@/components/MessageBubble";

export interface ChatController {
  messages: ChatMessage[];
  status: string | null;
  pending: boolean;
  quickReplies: string[];
  model: string | null;
  sessionId: string;
  send: (text: string) => Promise<void>;
}

function newSessionId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `sess-${Date.now()}`;
}

export function useChat(): ChatController {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [quickReplies, setQuickReplies] = useState<string[]>([]);
  const [model, setModel] = useState<string | null>(null);
  const sessionRef = useRef<string>(newSessionId());

  const send = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    setMessages((m) => [...m, { role: "user", text: trimmed }]);
    setQuickReplies([]);
    setStatus(null);
    setPending(true);

    // The assistant turn for this send; we push it on `message` and patch its
    // trace_id on `done` (trace_id is only known at stream end).
    let assistantIndex = -1;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          session_id: sessionRef.current,
          message: trimmed,
        }),
      });
      if (!res.body) throw new Error("no stream");

      for await (const ev of parseSse(res.body)) {
        switch (ev.type) {
          case "status":
            setStatus(ev.label);
            break;
          case "message": {
            const assistant: AssistantMessage = {
              role: "assistant",
              text: ev.text,
              blocked: ev.blocked,
              cards: ev.structured,
              citations: ev.citations,
              traceId: null,
            };
            // Session-level remembered appliance model (FR-5); null leaves it
            // unchanged so a later modelless turn doesn't clear the chip.
            if (ev.current_model) setModel(ev.current_model);
            setQuickReplies(ev.quick_replies);
            setMessages((m) => {
              assistantIndex = m.length;
              return [...m, assistant];
            });
            break;
          }
          case "done":
            setMessages((m) =>
              m.map((msg, i) =>
                i === assistantIndex && msg.role === "assistant"
                  ? { ...msg, traceId: ev.trace_id }
                  : msg,
              ),
            );
            break;
          case "error":
            setMessages((m) => [
              ...m,
              {
                role: "assistant",
                text: ev.message,
                blocked: true,
                cards: [],
                citations: [],
                traceId: ev.trace_id ?? null,
              },
            ]);
            break;
        }
      }
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: "Something went wrong reaching the assistant. Please try again.",
          blocked: true,
          cards: [],
          citations: [],
          traceId: null,
        },
      ]);
    } finally {
      setPending(false);
      setStatus(null);
    }
  }, []);

  return {
    messages,
    status,
    pending,
    quickReplies,
    model,
    sessionId: sessionRef.current,
    send,
  };
}
