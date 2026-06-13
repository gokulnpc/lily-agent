import type { Card } from "@/lib/types";
import { Cards } from "@/components/Cards";
import { Citations } from "@/components/Citations";
import { Feedback } from "@/components/Feedback";
import { Markdown } from "@/components/Markdown";
import { StreamingText } from "@/components/StreamingText";
import { TulipIcon } from "@/components/icons";

export interface AssistantMessage {
  role: "assistant";
  text: string;
  blocked: boolean;
  cards: Card[];
  citations: string[];
  traceId: string | null;
  streamComplete?: boolean;
}

export interface UserMessage {
  role: "user";
  text: string;
}

export type ChatMessage = UserMessage | AssistantMessage;

export function MessageBubble({
  message,
  sessionId,
  isStreaming,
  onStreamComplete,
}: {
  message: ChatMessage;
  sessionId: string;
  isStreaming?: boolean;
  onStreamComplete?: () => void;
}) {
  if (message.role === "user") {
    return (
      <div className="bubble bubble--user" data-testid="user-bubble">
        {message.text}
      </div>
    );
  }

  const showExtras = message.streamComplete === true;

  return (
    <div className="turn-assistant" data-testid="assistant-bubble">
      <div className="assistant-head">
        <TulipIcon size={18} />
        <span className="assistant-name">Lily</span>
      </div>
      {message.text &&
        (isStreaming ? (
          <StreamingText
            text={message.text}
            active
            onComplete={() => onStreamComplete?.()}
          />
        ) : (
          <div
            className={`bubble bubble--assistant md ${message.blocked ? "is-blocked" : ""} ${showExtras ? "is-complete" : ""}`}
          >
            <Markdown>{message.text}</Markdown>
          </div>
        ))}
      {showExtras && (
        <div className="turn-extras">
          <Cards cards={message.cards} />
          <Citations urls={message.citations} />
          <Feedback traceId={message.traceId} sessionId={sessionId} />
        </div>
      )}
    </div>
  );
}

export function AssistantHead() {
  return (
    <div className="assistant-head" data-testid="assistant-head">
      <TulipIcon size={18} />
      <span className="assistant-name">Lily</span>
    </div>
  );
}
