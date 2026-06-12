"use client";

import { useEffect, useRef, useState } from "react";
import { MessageBubble } from "@/components/MessageBubble";
import { QuickReplies } from "@/components/QuickReplies";
import { StatusChip } from "@/components/StatusChip";
import { useChat } from "@/lib/useChat";

const GREETING =
  "Hi, I’m Lily — your PartSelect assistant for refrigerator and dishwasher parts. " +
  "Tell me a symptom, a part number, or a model and I’ll help you find the fix.";

const EXAMPLES = [
  "How can I install part number PS11752778?",
  "Is PS11752778 compatible with my WDT780SAEM1?",
  "My Whirlpool fridge ice maker is not working.",
];

export function Chat() {
  const chat = useChat();
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && typeof el.scrollTo === "function") {
      el.scrollTo({ top: el.scrollHeight });
    }
  }, [chat.messages, chat.status]);

  function submit(text: string) {
    if (chat.pending) return;
    void chat.send(text);
    setInput("");
  }

  const empty = chat.messages.length === 0;

  return (
    <div className="chat">
      <div className="chat-scroll" ref={scrollRef} data-testid="chat-scroll">
        {empty ? (
          <div className="chat-empty">
            <p className="chat-greeting">{GREETING}</p>
            <div className="chat-examples">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  className="chat-example"
                  onClick={() => submit(ex)}
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="chat-messages">
            {chat.messages.map((m, i) => (
              <MessageBubble key={i} message={m} sessionId={chat.sessionId} />
            ))}
            {chat.pending && chat.status && <StatusChip label={chat.status} />}
            {!chat.pending && (
              <QuickReplies
                replies={chat.quickReplies}
                onPick={submit}
                disabled={chat.pending}
              />
            )}
          </div>
        )}
      </div>

      <form
        className="chat-input"
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about a part, model, symptom, or order…"
          aria-label="Message Lily"
          autoComplete="off"
          disabled={chat.pending}
        />
        <button type="submit" disabled={chat.pending || input.trim() === ""}>
          Send
        </button>
      </form>
    </div>
  );
}
