import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Markdown } from "@/components/Markdown";

const FIXTURE = [
  "Great news — the **Door Shelf Bin** is *really easy* to install:",
  "",
  "- Difficulty: **Really Easy**",
  "- Time: under 15 minutes",
  "",
  "See the [part page](https://www.partselect.com/PS11752778.htm) for details.",
  "",
  "> ⚠️ Before you begin, disconnect the power and shut off the water supply.",
  "",
  "# This heading must NOT render as a heading",
  "",
  "![nope](https://example.com/x.png) and <b>raw html</b> and <script>alert(1)</script>",
  "",
  "| a | b |",
  "|---|---|",
  "| 1 | 2 |",
].join("\n");

describe("Markdown (constrained)", () => {
  it("renders bold, italic, lists, blockquote, and links", () => {
    const { container } = render(<Markdown>{FIXTURE}</Markdown>);
    const strongs = [...container.querySelectorAll("strong")].map((e) => e.textContent);
    expect(strongs).toContain("Door Shelf Bin");
    expect(strongs).toContain("Really Easy");
    expect(container.querySelector("em")).toHaveTextContent("really easy");
    expect(container.querySelectorAll("li").length).toBeGreaterThanOrEqual(2);
    expect(container.querySelector("blockquote")).toHaveTextContent(/disconnect the power/);
  });

  it("opens links in a new tab, safely", () => {
    render(<Markdown>{FIXTURE}</Markdown>);
    const link = screen.getByRole("link", { name: "part page" });
    expect(link).toHaveAttribute("href", "https://www.partselect.com/PS11752778.htm");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("does NOT render headings, images, tables, or raw HTML", () => {
    const { container } = render(<Markdown>{FIXTURE}</Markdown>);
    // Heading unwrapped to text (still visible), not an <h1>.
    expect(container.querySelector("h1")).toBeNull();
    expect(container).toHaveTextContent("This heading must NOT render as a heading");
    // No images, no tables.
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("table")).toBeNull();
    // Raw HTML is escaped, not injected — no <script>/<b> nodes.
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(container).toHaveTextContent("raw html");
  });
});
