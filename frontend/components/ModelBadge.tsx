// Session context chip: the appliance model Lily is remembering for this
// conversation (FR-5). Set from the turn's `current_model` (the resolved/echoed
// model number, e.g. "WDT780SAEM1") — appears once the user has named a model.
export function ModelBadge({ model }: { model: string | null }) {
  if (!model) return null;
  return (
    <span className="model-badge" data-testid="model-badge">
      <span className="model-badge-label">Model</span>
      {model}
    </span>
  );
}
