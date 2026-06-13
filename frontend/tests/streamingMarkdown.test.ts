import { describe, expect, it } from "vitest";
import { safeMarkdownPrefix } from "@/lib/streamingMarkdown";

describe("safeMarkdownPrefix", () => {
  it("hides an unclosed bold span at the tail", () => {
    const full = "Great news — the **Refrigerator Door Shelf Bin** is easy!";
    const partial = safeMarkdownPrefix(full, full.indexOf("Bin") + 3);
    expect(partial).not.toContain("**");
    expect(partial).toBe("Great news — the ");
  });

  it("keeps a completed bold span", () => {
    const full = "Great news — the **Refrigerator Door Shelf Bin** is easy!";
    const end = full.indexOf("** is");
    const partial = safeMarkdownPrefix(full, end + 2);
    expect(partial).toContain("**Refrigerator Door Shelf Bin**");
  });

  it("strips incomplete link syntax", () => {
    const full = "See the [part page](https://example.com/page)";
    const partial = safeMarkdownPrefix(full, "See the [part pa".length);
    expect(partial).toBe("See the ");
  });
});
