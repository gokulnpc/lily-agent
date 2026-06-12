// Session current-model badge. The gateway reports the model that handled the
// turn (Haiku router vs Sonnet specialist); we surface the short tier name.
function shortName(modelId: string): string {
  const id = modelId.toLowerCase();
  if (id.includes("sonnet")) return "Sonnet 4.6";
  if (id.includes("haiku")) return "Haiku 4.5";
  return modelId;
}

export function ModelBadge({ model }: { model: string | null }) {
  if (!model) return null;
  return (
    <span className="model-badge" data-testid="model-badge">
      {shortName(model)}
    </span>
  );
}
