import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  AlertCircleIcon,
  AlertTriangleIcon,
  ArrowRightIcon,
  CartIcon,
  CheckIcon,
  ExternalLinkIcon,
  LightbulbIcon,
  ModelIcon,
  RefreshIcon,
  SendIcon,
  StarIcon,
  ThumbsDownIcon,
  ThumbsUpIcon,
  TulipIcon,
  TulipIconEmpty,
  TulipMark,
  WrenchIcon,
} from "@/components/icons";

describe("brand icons", () => {
  it("render as a 24-grid svg at the requested size", () => {
    const { container } = render(<SendIcon size={20} />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("width")).toBe("20");
    expect(svg?.getAttribute("viewBox")).toBe("0 0 24 24");
  });

  it("TulipMark wraps the glyph in the teal mark", () => {
    const { container } = render(<TulipMark size={24} />);
    expect(container.querySelector(".tulip-mark")).not.toBeNull();
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("TulipIcon renders inline brand tulip", () => {
    const { container } = render(<TulipIcon size={30} />);
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("every brand icon renders an svg", () => {
    for (const Icon of [
      SendIcon,
      StarIcon,
      ThumbsUpIcon,
      ThumbsDownIcon,
      ArrowRightIcon,
      CartIcon,
      CheckIcon,
      ModelIcon,
      ExternalLinkIcon,
      AlertTriangleIcon,
      WrenchIcon,
      LightbulbIcon,
      RefreshIcon,
      AlertCircleIcon,
      TulipIconEmpty,
    ]) {
      const { container } = render(<Icon size={16} />);
      expect(container.querySelector("svg")).not.toBeNull();
    }
  });
});
