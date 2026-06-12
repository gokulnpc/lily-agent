// Deterministic suggested-action chips (FR-12). Clicking one sends its label as
// the next user turn.
export function QuickReplies({
  replies,
  onPick,
  disabled,
}: {
  replies: string[];
  onPick: (label: string) => void;
  disabled?: boolean;
}) {
  if (replies.length === 0) return null;
  return (
    <div className="quick-replies" data-testid="quick-replies">
      {replies.map((label, i) => (
        <button
          key={`${label}-${i}`}
          type="button"
          className="quick-reply"
          disabled={disabled}
          onClick={() => onPick(label)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
