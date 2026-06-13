"use client";

import { useCallback, useRef, useState } from "react";
import { parseSse } from "@/lib/sse";
import type { AssistantMessage, ChatMessage } from "@/components/MessageBubble";

export type StreamPhase = "idle" | "loading" | "streaming" | "complete";

export interface ChatError {
  message: string;
  traceId: string | null;
}

export interface ChatController {
  messages: ChatMessage[];
  status: string | null;
  pending: boolean;
  streamPhase: StreamPhase;
  streamingMessageIndex: number | null;
  error: ChatError | null;
  quickReplies: string[];
  model: string | null;
  sessionId: string;
  lastUserMessage: string | null;
  send: (text: string) => Promise<void>;
  completeStreaming: () => void;
  clearError: () => void;
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
  const [streamPhase, setStreamPhase] = useState<StreamPhase>("idle");
  const [streamingMessageIndex, setStreamingMessageIndex] = useState<number | null>(null);
  const [error, setError] = useState<ChatError | null>(null);
  const [quickReplies, setQuickReplies] = useState<string[]>([]);
  const [model, setModel] = useState<string | null>(null);
  const [lastUserMessage, setLastUserMessage] = useState<string | null>(null);
  const sessionRef = useRef<string>(newSessionId());

  const completeStreaming = useCallback(() => {
    setStreamPhase("complete");
    setStreamingMessageIndex((idx) => {
      if (idx !== null) {
        setMessages((m) =>
          m.map((msg, i) =>
            i === idx && msg.role === "assistant"
              ? { ...msg, streamComplete: true }
              : msg,
          ),
        );
      }
      return null;
    });
  }, []);

  const clearError = useCallback(() => setError(null), []);

  const send = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    setError(null);
    setLastUserMessage(trimmed);
    setMessages((m) => [...m, { role: "user", text: trimmed }]);
    setQuickReplies([]);
    setStatus(null);
    setPending(true);
    setStreamPhase("loading");

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
            setStreamPhase("loading");
            break;
          case "message": {
            const hasText = Boolean(ev.text?.trim());
            const assistant: AssistantMessage = {
              role: "assistant",
              text: ev.text,
              blocked: ev.blocked,
              cards: ev.structured,
              citations: ev.citations,
              traceId: null,
              streamComplete: !hasText,
            };
            if (ev.current_model) setModel(ev.current_model);
            setQuickReplies(ev.quick_replies);
            setMessages((m) => {
              assistantIndex = m.length;
              if (hasText) {
                setStreamingMessageIndex(m.length);
                setStreamPhase("streaming");
              } else {
                setStreamPhase("complete");
              }
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
            setError({
              message: ev.message,
              traceId: ev.trace_id ?? null,
            });
            setStreamPhase("idle");
            break;
        }
      }
    } catch {
      setError({
        message: "Something went wrong reaching the assistant. Please try again.",
        traceId: null,
      });
      setStreamPhase("idle");
    } finally {
      setPending(false);
      setStatus(null);
    }
  }, []);

  return {
    messages,
    status,
    pending,
    streamPhase,
    streamingMessageIndex,
    error,
    quickReplies,
    model,
    sessionId: sessionRef.current,
    lastUserMessage,
    send,
    completeStreaming,
    clearError,
  };
}
