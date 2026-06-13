import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Constrained Markdown for assistant prose: bold / italic / lists / blockquote /
// links only. Disallowed elements (headings, images, tables, raw HTML) are
// unwrapped to their text — never rendered — so a stray `#` or markdown table from
// the model degrades to plain text instead of injecting structure or markup.
// react-markdown does not render raw HTML by default (no rehype-raw), so no HTML
// injection surface. Links always open in a new tab, safely.
const ALLOWED = ["p", "strong", "em", "ul", "ol", "li", "blockquote", "a", "br"];

export function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      allowedElements={ALLOWED}
      unwrapDisallowed
      components={{
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer">
            {children}
          </a>
        ),
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
