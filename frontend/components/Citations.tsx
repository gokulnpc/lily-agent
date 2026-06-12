// FR-19 — every RAG-backed answer carries source links. Rendered as chips under
// the message text. Labels show the host so the source is legible at a glance.
function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function Citations({ urls }: { urls: string[] }) {
  if (urls.length === 0) return null;
  return (
    <div className="citations" data-testid="citations">
      <span className="citations-label">Sources:</span>
      {urls.map((url, i) => (
        <a
          key={`${url}-${i}`}
          className="citation-chip"
          href={url}
          target="_blank"
          rel="noopener noreferrer"
        >
          {hostOf(url)}
        </a>
      ))}
    </div>
  );
}
