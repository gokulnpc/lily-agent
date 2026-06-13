import type { ReactNode } from "react";

// Icons from the Lily Brand Spec. Lucide-style line icons: viewBox 0 0 24 24,
// fill none, stroke currentColor, stroke-width 2.1, round caps. Star and the
// tulip mark are filled. Decorative (aria-hidden); buttons carry their own labels.

interface IconProps {
  size?: number;
  className?: string;
}

function Line({
  size = 18,
  className,
  children,
}: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.1}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export function SendIcon(p: IconProps) {
  return (
    <Line {...p}>
      <path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7Z" />
    </Line>
  );
}

export function ArrowRightIcon(p: IconProps) {
  return (
    <Line {...p}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </Line>
  );
}

export function CartIcon(p: IconProps) {
  return (
    <Line {...p}>
      <circle cx="9" cy="21" r="1.4" />
      <circle cx="18" cy="21" r="1.4" />
      <path d="M1 1h3l2.6 12.4a2 2 0 0 0 2 1.6h8.7a2 2 0 0 0 2-1.6L23 6H6" />
    </Line>
  );
}

export function CheckIcon(p: IconProps) {
  return (
    <Line {...p}>
      <path d="M20 6 9 17l-5-5" />
    </Line>
  );
}

export function WrenchIcon(p: IconProps) {
  return (
    <Line {...p}>
      <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4l-6 6a1.4 1.4 0 0 0 2 2l6-6a4 4 0 0 0 5.4-5.4l-2.3 2.3-2-2 2.3-2.3Z" />
    </Line>
  );
}

export function LightbulbIcon(p: IconProps) {
  return (
    <Line {...p}>
      <path d="M9.7 17h4.6M12 3a6 6 0 0 0-4 10.5c.6.6 1 1.3 1 2.1h6c0-.8.4-1.5 1-2.1A6 6 0 0 0 12 3Z" />
    </Line>
  );
}

export function RefreshIcon(p: IconProps) {
  return (
    <Line {...p}>
      <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
      <path d="M3 3v5h5" />
    </Line>
  );
}

export function AlertCircleIcon(p: IconProps) {
  return (
    <Line {...p}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v5M12 16h.01" />
    </Line>
  );
}

export function ThumbsUpIcon(p: IconProps) {
  return (
    <svg
      width={p.size ?? 18}
      height={p.size ?? 18}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={p.className}
      aria-hidden="true"
    >
      <path d="M7 22H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1h3Zm3.5-12 1.2-5.4A2 2 0 0 1 13.6 3c1 0 1.8.9 1.6 1.9L14.5 9H20a2 2 0 0 1 2 2.3l-1.2 7A2 2 0 0 1 18.8 20H9V10Z" />
    </svg>
  );
}

export function ThumbsDownIcon(p: IconProps) {
  return (
    <svg
      width={p.size ?? 18}
      height={p.size ?? 18}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={p.className}
      aria-hidden="true"
    >
      <path d="M17 2h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-3Zm-3.5 12-1.2 5.4A2 2 0 0 1 10.4 21c-1 0-1.8-.9-1.6-1.9L9.5 15H4a2 2 0 0 1-2-2.3l1.2-7A2 2 0 0 1 5.2 4H15v10Z" />
    </svg>
  );
}

export function ModelIcon(p: IconProps) {
  return (
    <Line {...p}>
      <rect x="5" y="2" width="14" height="20" rx="2" />
      <line x1="9" y1="6" x2="9" y2="9" />
      <line x1="9" y1="13" x2="9" y2="13" />
    </Line>
  );
}

export function ExternalLinkIcon(p: IconProps) {
  return (
    <Line {...p}>
      <path d="M7 17 17 7M9 7h8v8" />
    </Line>
  );
}

export function AlertTriangleIcon(p: IconProps) {
  return (
    <Line {...p}>
      <path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
    </Line>
  );
}

// Filled rating star.
export function StarIcon({ size = 14, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      aria-hidden="true"
    >
      <path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1Z" />
    </svg>
  );
}

// Inline tulip (header, assistant head, empty state) — teal petals, accent center, stem.
export function TulipIcon({ size = 24, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M20 7 C 18 9.6 16.8 12 16.8 14.2 C 14.6 11.6 11.8 10.6 9.6 11.6 C 9 14.8 10.2 18.4 13 21 C 15.4 23.2 17.7 24.2 20 24.2 C 22.3 24.2 24.6 23.2 27 21 C 29.8 18.4 31 14.8 30.4 11.6 C 28.2 10.6 25.4 11.6 23.2 14.2 C 23.2 12 22 9.6 20 7 Z"
        fill="var(--ps-primary)"
      />
      <path
        d="M20 10.8 C 18.9 12.7 18.3 14.1 18.3 15.6 C 18.9 16.9 19.4 17.6 20 18.2 C 20.6 17.6 21.1 16.9 21.7 15.6 C 21.7 14.1 21.1 12.7 20 10.8 Z"
        fill="var(--ps-accent)"
      />
      <path
        d="M20 24 L20 33"
        stroke="var(--ps-primary)"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
      <path
        d="M20 29.6 C 16.5 28.6 13.8 30.1 12.8 33.1 C 16.3 33.3 18.7 32.1 20 29.9 Z"
        fill="var(--ps-primary)"
      />
    </svg>
  );
}

// Empty-state tulip: white center petal on accent card background.
export function TulipIconEmpty({ size = 44, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M20 7 C 18 9.6 16.8 12 16.8 14.2 C 14.6 11.6 11.8 10.6 9.6 11.6 C 9 14.8 10.2 18.4 13 21 C 15.4 23.2 17.7 24.2 20 24.2 C 22.3 24.2 24.6 23.2 27 21 C 29.8 18.4 31 14.8 30.4 11.6 C 28.2 10.6 25.4 11.6 23.2 14.2 C 23.2 12 22 9.6 20 7 Z"
        fill="var(--ps-primary)"
      />
      <path
        d="M20 10.8 C 18.9 12.7 18.3 14.1 18.3 15.6 C 18.9 16.9 19.4 17.6 20 18.2 C 20.6 17.6 21.1 16.9 21.7 15.6 C 21.7 14.1 21.1 12.7 20 10.8 Z"
        fill="#fff"
      />
      <path
        d="M20 24 L20 33"
        stroke="var(--ps-primary)"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
      <path
        d="M20 29.6 C 16.5 28.6 13.8 30.1 12.8 33.1 C 16.3 33.3 18.7 32.1 20 29.9 Z"
        fill="var(--ps-primary)"
      />
    </svg>
  );
}

// Brand mark: a white tulip glyph on a teal rounded square (.tulip-mark).
export function TulipMark({ size = 24, className }: IconProps) {
  return (
    <span
      className={`tulip-mark${className ? ` ${className}` : ""}`}
      style={{ width: size, height: size, borderRadius: Math.round(size * 0.28) }}
      aria-hidden="true"
    >
      <svg width={size * 0.74} height={size * 0.74} viewBox="0 0 40 40" fill="none">
        <path
          d="M20 7 C 18 9.6 16.8 12 16.8 14.2 C 14.6 11.6 11.8 10.6 9.6 11.6 C 9 14.8 10.2 18.4 13 21 C 15.4 23.2 17.7 24.2 20 24.2 C 22.3 24.2 24.6 23.2 27 21 C 29.8 18.4 31 14.8 30.4 11.6 C 28.2 10.6 25.4 11.6 23.2 14.2 C 23.2 12 22 9.6 20 7 Z"
          fill="#FFFFFF"
        />
        <path
          d="M20 10.8 C 18.9 12.7 18.3 14.1 18.3 15.6 C 18.9 16.9 19.4 17.6 20 18.2 C 20.6 17.6 21.1 16.9 21.7 15.6 C 21.7 14.1 21.1 12.7 20 10.8 Z"
          fill="var(--ps-primary)"
        />
      </svg>
    </span>
  );
}
