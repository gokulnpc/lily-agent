import { AlertCircleIcon, RefreshIcon } from "@/components/icons";

const PARTSELECT_URL = "https://www.partselect.com/";

export function ErrorCard({
  title = "Lily couldn't reach the catalog just now",
  subtitle = "Your question wasn't lost. Try again, or browse parts on PartSelect.",
  traceId,
  onRetry,
}: {
  title?: string;
  subtitle?: string;
  traceId?: string | null;
  onRetry?: () => void;
}) {
  return (
    <div className="error-card" data-testid="error-card" role="alert">
      <div className="error-card-body">
        <span className="error-icon-wrap">
          <AlertCircleIcon size={18} />
        </span>
        <div>
          <p className="error-title">{title}</p>
          <p className="error-subtitle">{subtitle}</p>
          <div className="error-actions">
            {onRetry && (
              <button type="button" className="btn btn-primary" onClick={onRetry}>
                <RefreshIcon size={14} />
                Try again
              </button>
            )}
            <a
              className="btn btn-secondary"
              href={PARTSELECT_URL}
              target="_blank"
              rel="noopener noreferrer"
            >
              Browse on PartSelect
            </a>
          </div>
        </div>
      </div>
      {traceId && (
        <div className="error-footer" data-testid="error-trace">
          trace_id · {traceId}
        </div>
      )}
    </div>
  );
}
