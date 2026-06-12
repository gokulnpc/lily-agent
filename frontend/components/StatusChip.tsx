// Ephemeral per-node progress (the `status` events), e.g. "Checking compatibility…".
// Shown while a turn is in flight; replaced by the assistant message when `done`.
export function StatusChip({ label }: { label: string }) {
  return (
    <div className="status-chip" role="status" data-testid="status-chip">
      <span className="status-dots" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      {label}
    </div>
  );
}
