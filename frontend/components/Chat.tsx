"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AssistantHead, MessageBubble } from "@/components/MessageBubble";
import { ErrorCard } from "@/components/ErrorCard";
import { ModelBadge } from "@/components/ModelBadge";
import { QuickReplies } from "@/components/QuickReplies";
import { StatusChip } from "@/components/StatusChip";
import {
  CheckIcon,
  LightbulbIcon,
  SendIcon,
  TulipIcon,
  TulipIconEmpty,
  WrenchIcon,
} from "@/components/icons";
import { useChat } from "@/lib/useChat";

const GREETING = "Hi, I'm Lily.";
const GREETING_SUB =
  "I help you find, fit, and install refrigerator & dishwasher parts — every answer grounded in PartSelect's catalog, never guessed.";

const EXAMPLES: { text: string; icon: "wrench" | "check" | "lightbulb" }[] = [
  { text: "How do I install part PS11752778?", icon: "wrench" },
  { text: "Is PS11752778 compatible with my model?", icon: "check" },
  { text: "My Whirlpool ice maker isn't working", icon: "lightbulb" },
];

function ExampleIcon({ kind }: { kind: "wrench" | "check" | "lightbulb" }) {
  if (kind === "wrench") return <WrenchIcon size={17} />;
  if (kind === "check") return <CheckIcon size={17} />;
  return <LightbulbIcon size={17} />;
}

export function Chat() {
  const chat = useChat();
  const {
    messages,
    status,
    pending,
    streamPhase,
    streamingMessageIndex,
    error,
    quickReplies,
    model,
    sessionId,
    lastUserMessage,
    send,
    completeStreaming,
    clearError,
  } = chat;
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && typeof el.scrollTo === "function") {
      el.scrollTo({ top: el.scrollHeight });
    }
  }, [messages, status, streamPhase, error]);

  function submit(text: string) {
    if (pending) return;
    void send(text);
    setInput("");
  }

  const handleStreamComplete = useCallback(() => {
    completeStreaming();
  }, [completeStreaming]);

  const empty = messages.length === 0 && !error;
  const showLoading = pending && streamPhase === "loading" && status;

  return (
    <>
      <header className="app-header">
        <div className="brand">
          <TulipIcon size={30} />
          <span className="brand-name">Lily</span>
          <span className="brand-tag">Refrigerator &amp; dishwasher parts</span>
        </div>
        {model && <ModelBadge model={model} />}
      </header>

      <div className="chat">
        <div className="chat-scroll" ref={scrollRef} data-testid="chat-scroll">
          <div className="chat-column">
            {empty ? (
              <div className="chat-empty">
                <div className="chat-empty-card">
                  <TulipIconEmpty size={44} />
                  <h1 className="chat-greeting">{GREETING}</h1>
                  <p className="chat-greeting-sub">{GREETING_SUB}</p>
                  <span className="chat-examples-label">Try asking</span>
                  <div className="chat-examples">
                    {EXAMPLES.map((ex) => (
                      <button
                        key={ex.text}
                        type="button"
                        className="chat-example"
                        onClick={() => submit(ex.text)}
                      >
                        <ExampleIcon kind={ex.icon} />
                        {ex.text}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="chat-messages">
                {messages.map((m, i) => (
                  <MessageBubble
                    key={i}
                    message={m}
                    sessionId={sessionId}
                    isStreaming={streamPhase === "streaming" && streamingMessageIndex === i}
                    onStreamComplete={handleStreamComplete}
                  />
                ))}
                {showLoading && (
                  <div className="status-row">
                    <AssistantHead />
                    <StatusChip label={status!} />
                  </div>
                )}
                {error && (
                  <ErrorCard
                    title={
                      error.message.includes("unreachable") ||
                      error.message.includes("went wrong")
                        ? "Lily couldn't reach the catalog just now"
                        : undefined
                    }
                    subtitle={error.message}
                    traceId={error.traceId}
                    onRetry={
                      lastUserMessage
                        ? () => {
                            clearError();
                            void send(lastUserMessage);
                          }
                        : undefined
                    }
                  />
                )}
                {streamPhase === "complete" && !pending && (
                  <QuickReplies replies={quickReplies} onPick={submit} disabled={pending} />
                )}
              </div>
            )}
          </div>
        </div>

        <form
          className="chat-input"
          onSubmit={(e) => {
            e.preventDefault();
            submit(input);
          }}
        >
          <div className="chat-column chat-input-row">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about a part, model, symptom, or order…"
              aria-label="Message Lily"
              autoComplete="off"
              disabled={pending}
            />
            <button type="submit" disabled={pending || input.trim() === ""}>
              Send
              <SendIcon size={16} />
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
