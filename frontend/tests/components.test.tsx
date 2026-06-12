import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Citations } from "@/components/Citations";
import { Feedback } from "@/components/Feedback";
import { ModelBadge } from "@/components/ModelBadge";
import { QuickReplies } from "@/components/QuickReplies";
import { StatusChip } from "@/components/StatusChip";

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

describe("Citations", () => {
  it("renders one chip per URL labelled by host", () => {
    render(<Citations urls={["https://www.partselect.com/PS1.htm"]} />);
    const link = screen.getByRole("link", { name: "partselect.com" });
    expect(link).toHaveAttribute("href", "https://www.partselect.com/PS1.htm");
  });

  it("renders nothing when there are no citations", () => {
    const { container } = render(<Citations urls={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("ModelBadge", () => {
  it("maps the Sonnet inference profile to a short tier name", () => {
    render(<ModelBadge model="global.anthropic.claude-sonnet-4-6" />);
    expect(screen.getByTestId("model-badge")).toHaveTextContent("Sonnet 4.6");
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

    // Buttons disable after a pick.
    expect(screen.getByRole("button", { name: "Not helpful" })).toBeDisabled();
  });

  it("renders nothing without a trace_id", () => {
    const { container } = render(<Feedback traceId={null} sessionId="s1" />);
    expect(container).toBeEmptyDOMElement();
  });
});
