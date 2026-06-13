import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Citations } from "@/components/Citations";
import { Feedback } from "@/components/Feedback";
import { ModelBadge } from "@/components/ModelBadge";
import { QuickReplies } from "@/components/QuickReplies";
import { StatusChip } from "@/components/StatusChip";
import { StreamingText } from "@/components/StreamingText";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("StatusChip", () => {
  it("shows the node label", () => {
    render(<StatusChip label="Checking compatibility…" />);
    expect(screen.getByTestId("status-chip")).toHaveTextContent("Checking compatibility…");
  });
});

describe("StreamingText", () => {
  it("reveals text and calls onComplete", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const onComplete = vi.fn();
    render(<StreamingText text="Hello" active onComplete={onComplete} />);
    expect(screen.getByTestId("streaming-text")).toHaveTextContent("");
    await vi.runAllTimersAsync();
    expect(onComplete).toHaveBeenCalled();
    vi.useRealTimers();
  });
});

describe("Citations", () => {
  it("renders primary and secondary citation chips", () => {
    render(
      <Citations
        urls={[
          "https://www.partselect.com/PS1.htm",
          "https://www.youtube.com/watch?v=abc",
        ]}
      />,
    );
    expect(screen.getByText("Sources")).toBeInTheDocument();
    const primary = screen.getByRole("link", { name: "partselect.com" });
    expect(primary).toHaveClass("citation-chip--primary");
    const secondary = screen.getByRole("link", { name: /youtube\.com/ });
    expect(secondary).toHaveClass("citation-chip--secondary");
  });

  it("renders nothing when there are no citations", () => {
    const { container } = render(<Citations urls={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("ModelBadge", () => {
  it("shows the remembered appliance model with the device icon (FR-5)", () => {
    render(<ModelBadge model="WDT780SAEM1" />);
    const badge = screen.getByTestId("model-badge");
    expect(badge).toHaveTextContent("WDT780SAEM1");
    expect(badge.querySelector("svg")).not.toBeNull();
  });

  it("renders nothing without a model", () => {
    const { container } = render(<ModelBadge model={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("QuickReplies", () => {
  it("invokes onPick with the chosen label", () => {
    const onPick = vi.fn();
    render(<QuickReplies replies={["Compare parts"]} onPick={onPick} />);
    fireEvent.click(screen.getByRole("button", { name: "Compare parts" }));
    expect(onPick).toHaveBeenCalledWith("Compare parts");
  });
});

describe("Feedback", () => {
  it("POSTs the rating keyed to the trace_id and locks after a pick", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ({
      ok: true,
      status: 204,
    }));
    vi.stubGlobal("fetch", fetchMock);

    render(<Feedback traceId="trace-abc" sessionId="s1" />);
    fireEvent.click(screen.getByRole("button", { name: "Helpful" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/feedback",
      expect.objectContaining({ method: "POST" }),
    );
    const body = JSON.parse(fetchMock.mock.calls[0][1]!.body as string);
    expect(body).toMatchObject({ trace_id: "trace-abc", session_id: "s1", rating: "up" });

    expect(screen.getByRole("button", { name: "Not helpful" })).toBeDisabled();
  });

  it("renders nothing without a trace_id", () => {
    const { container } = render(<Feedback traceId={null} sessionId="s1" />);
    expect(container).toBeEmptyDOMElement();
  });
});
