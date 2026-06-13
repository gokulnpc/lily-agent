import { ExternalLinkIcon } from "@/components/icons";

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
      <span className="citations-label">Sources</span>
      {urls.map((url, i) => {
        const host = hostOf(url);
        const isPrimary = i === 0;
        return (
          <a
            key={`${url}-${i}`}
            className={`citation-chip ${isPrimary ? "citation-chip--primary" : "citation-chip--secondary"}`}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
          >
            {isPrimary && <span className="citation-dot" aria-hidden="true" />}
            {host}
            {!isPrimary && <ExternalLinkIcon size={11} />}
          </a>
        );
      })}
    </div>
  );
}
