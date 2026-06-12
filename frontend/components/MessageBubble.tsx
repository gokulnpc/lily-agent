import type { Card } from "@/lib/types";
import { Cards } from "@/components/Cards";
import { Citations } from "@/components/Citations";
import { Feedback } from "@/components/Feedback";

export interface AssistantMessage {
  role: "assistant";
  text: string;
  blocked: boolean;
  cards: Card[];
  citations: string[];
  traceId: string | null;
}

export interface UserMessage {
  role: "user";
  text: string;
}

export type ChatMessage = UserMessage | AssistantMessage;

export function MessageBubble({
  message,
  sessionId,
}: {
  message: ChatMessage;
  sessionId: string;
}) {
  if (message.role === "user") {
    return (
      <div className="bubble bubble--user" data-testid="user-bubble">
        {message.text}
      </div>
    );
  }
  return (
    <div className="turn-assistant" data-testid="assistant-bubble">
      <div className="assistant-head">
        <span className="assistant-name">Lily</span>
      </div>
      {message.text && (
        <div className={`bubble bubble--assistant ${message.blocked ? "is-blocked" : ""}`}>
          {message.text}
        </div>
      )}
      <Cards cards={message.cards} />
      <Citations urls={message.citations} />
      <Feedback traceId={message.traceId} sessionId={sessionId} />
    </div>
  );
}
