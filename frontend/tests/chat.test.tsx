import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Chat } from "@/components/Chat";
import { frame, sampleProduct, sseStream } from "./helpers";

const TURN_WIRE =
  frame("status", { node: "router", label: "Routing…" }) +
  frame("status", { node: "compatibility", label: "Checking compatibility…" }) +
  frame("message", {
    text: "No — that part doesn’t fit. Here’s the right one:",
    primary_intent: "compatibility",
    blocked: false,
    invalid_identifiers: [],
    citations: ["https://www.partselect.com/PS11752778-Door-Shelf-Bin.htm"],
    structured: [sampleProduct],
    quick_replies: ["How do I install the Door Shelf Bin?"],
    current_model: "global.anthropic.claude-sonnet-4-6",
    trace: [],
  }) +
  frame("done", { session_id: "s1", trace_id: "trace-abc" });

function mockChatFetch(wire: string) {
  return vi.fn(async (url: string, _init?: RequestInit) => {
    if (String(url).includes("/api/feedback")) {
      return { ok: true, status: 204 };
    }
    return {
      ok: true,
      body: sseStream(wire),
      headers: new Headers({ "x-trace-id": "trace-abc" }),
    };
  });
}

function bodyOf(call: [string, RequestInit?]): { message: string; session_id: string } {
  return JSON.parse(call[1]!.body as string);
}

function ask(text: string) {
  fireEvent.change(screen.getByLabelText("Message Lily"), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Chat (mocked SSE)", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", mockChatFetch(TURN_WIRE));
  });

  it("renders the user turn, assistant text, product card, citation, model badge, and quick reply", async () => {
    render(<Chat />);
    ask("Is PS11752778 compatible with my WDT780SAEM1?");

    expect(screen.getByTestId("user-bubble")).toHaveTextContent("Is PS11752778 compatible");

    await screen.findByText(/that part doesn’t fit/);
    expect(screen.getByTestId("product-card")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "partselect.com" })).toBeInTheDocument();
    expect(screen.getByTestId("model-badge")).toHaveTextContent("Sonnet 4.6");
    expect(
      screen.getByRole("button", { name: "How do I install the Door Shelf Bin?" }),
    ).toBeInTheDocument();

    // Feedback appears once `done` supplies the trace_id.
    await waitFor(() => expect(screen.getByTestId("feedback")).toBeInTheDocument());
  });

  it("sends a quick-reply label as the next turn", async () => {
    const fetchMock = mockChatFetch(TURN_WIRE);
    vi.stubGlobal("fetch", fetchMock);

    render(<Chat />);
    ask("Is PS11752778 compatible with my WDT780SAEM1?");
    const chip = await screen.findByRole("button", {
      name: "How do I install the Door Shelf Bin?",
    });

    fireEvent.click(chip);

    await waitFor(() => {
      const chatCalls = fetchMock.mock.calls.filter((c) => String(c[0]).includes("/api/chat"));
      expect(chatCalls.length).toBe(2);
    });
    const secondCall = fetchMock.mock.calls.filter((c) =>
      String(c[0]).includes("/api/chat"),
    )[1];
    expect(bodyOf(secondCall).message).toBe("How do I install the Door Shelf Bin?");
  });

  it("renders an error frame as a user-facing message", async () => {
    vi.stubGlobal(
      "fetch",
      mockChatFetch(
        frame("error", {
          message: "The assistant is unreachable right now. Please try again.",
          trace_id: "trace-err",
        }),
      ),
    );

    render(<Chat />);
    ask("hello");
    await screen.findByText(/unreachable right now/);
  });

  it("keeps session_id stable across turns", async () => {
    const fetchMock = mockChatFetch(TURN_WIRE);
    vi.stubGlobal("fetch", fetchMock);

    render(<Chat />);
    ask("first");
    await screen.findByText(/that part doesn’t fit/);
    ask("second");

    await waitFor(() => {
      const chatCalls = fetchMock.mock.calls.filter((c) => String(c[0]).includes("/api/chat"));
      expect(chatCalls.length).toBe(2);
    });
    const chatCalls = fetchMock.mock.calls.filter((c) => String(c[0]).includes("/api/chat"));
    expect(bodyOf(chatCalls[0]).session_id).toBe(bodyOf(chatCalls[1]).session_id);
  });
});
