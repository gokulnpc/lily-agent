/** Return a prefix of `source` safe to pass to react-markdown while text is still revealing. */
export function safeMarkdownPrefix(source: string, visibleChars: number): string {
  let text = source.slice(0, Math.max(0, visibleChars));

  // Incomplete markdown link: [label](partial-url or [partial-label
  text = text.replace(/\[[^\]]*\]\([^)]*$/, "");
  text = text.replace(/\[[^\]]*$/, "");

  // Unclosed **bold** — odd segment count after splitting on **
  const boldParts = text.split("**");
  if (boldParts.length % 2 === 0) {
    text = boldParts.slice(0, -1).join("**");
  }

  // Trailing single * opening italic (skip when string ends with **)
  if (!text.endsWith("**")) {
    text = text.replace(/(\S)\*(?!\*)$/, "$1");
  }

  // Trailing _ opening italic
  text = text.replace(/(\S)_$/, "$1");

  return text;
}
