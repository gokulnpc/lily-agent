import { ModelIcon } from "@/components/icons";

// Session context chip: the appliance model Lily is remembering for this
// conversation (FR-5). Set from the turn's `current_model` (e.g. "WDT780SAEM1"),
// shown with the device icon in the header once the user has named a model.
export function ModelBadge({ model }: { model: string | null }) {
  if (!model) return null;
  return (
    <span className="model-badge" data-testid="model-badge">
      <ModelIcon size={15} />
      {model}
    </span>
  );
}
