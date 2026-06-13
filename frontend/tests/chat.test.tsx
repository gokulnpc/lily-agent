import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Chat } from "@/components/Chat";
import { frame, sampleProduct, sseStream } from "./helpers";

const TURN_WIRE =
  frame("status", { node: "router", label: "Routing…" }) +
  frame("status", { node: "compatibility", label: "Checking compatibility…" }) +
  frame("message", {
    text: "No — that part doesn't fit. Here's the right one:",
    primary_intent: "compatibility",
    blocked: false,
    invalid_identifiers: [],
    citations: ["https://www.partselect.com/PS11752778-Door-Shelf-Bin.htm"],
    structured: [sampleProduct],
    quick_replies: ["How do I install the Door Shelf Bin?"],
    current_model: "WDT780SAEM1",
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

  it("renders the golden empty state with starter chips", () => {
    render(<Chat />);
    expect(screen.getByText("Hi, I'm Lily.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /How do I install part PS11752778/ })).toBeInTheDocument();
    expect(document.querySelector(".chat-empty-card")).not.toBeNull();
  });

  it("renders the user turn, assistant text, product card, citation, model badge, and quick reply", async () => {
    render(<Chat />);
    ask("Is PS11752778 compatible with my WDT780SAEM1?");

    expect(screen.getByTestId("user-bubble")).toHaveTextContent("Is PS11752778 compatible");

    await waitFor(
      () => {
        expect(screen.getByText(/that part doesn't fit/)).toBeInTheDocument();
        expect(screen.getByTestId("product-card")).toBeInTheDocument();
      },
      { timeout: 5000 },
    );
    expect(screen.getByRole("link", { name: "partselect.com" })).toBeInTheDocument();
    expect(screen.getByTestId("model-badge")).toHaveTextContent("WDT780SAEM1");
    expect(
      screen.getByRole("button", { name: "How do I install the Door Shelf Bin?" }),
    ).toBeInTheDocument();

    await waitFor(() => expect(screen.getByTestId("feedback")).toBeInTheDocument());
  });

  it("shows assistant head and status chip while loading", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(
              new TextEncoder().encode(
                frame("status", { node: "compatibility", label: "Checking compatibility…" }),
              ),
            );
          },
        }),
        headers: new Headers(),
      })),
    );

    render(<Chat />);
    ask("hello");

    await waitFor(() => {
      expect(screen.getByTestId("assistant-head")).toBeInTheDocument();
      expect(screen.getByTestId("status-chip")).toHaveTextContent("Checking compatibility");
    });
  });

  it("sends a quick-reply label as the next turn", async () => {
    const fetchMock = mockChatFetch(TURN_WIRE);
    vi.stubGlobal("fetch", fetchMock);

    render(<Chat />);
    ask("Is PS11752778 compatible with my WDT780SAEM1?");

    const chip = await screen.findByRole(
      "button",
      { name: "How do I install the Door Shelf Bin?" },
      { timeout: 5000 },
    );

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

  it("renders an error frame as ErrorCard with trace footer", async () => {
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
    await screen.findByTestId("error-card");
    expect(screen.getByText(/unreachable right now/)).toBeInTheDocument();
    expect(screen.getByTestId("error-trace")).toHaveTextContent("trace-err");
  });

  it("keeps session_id stable across turns", async () => {
    const fetchMock = mockChatFetch(TURN_WIRE);
    vi.stubGlobal("fetch", fetchMock);

    render(<Chat />);
    ask("first");
    await screen.findByText(/that part doesn't fit/, undefined, { timeout: 5000 });
    ask("second");

    await waitFor(() => {
      const chatCalls = fetchMock.mock.calls.filter((c) => String(c[0]).includes("/api/chat"));
      expect(chatCalls.length).toBe(2);
    });
    const chatCalls = fetchMock.mock.calls.filter((c) => String(c[0]).includes("/api/chat"));
    expect(bodyOf(chatCalls[0]).session_id).toBe(bodyOf(chatCalls[1]).session_id);
  });
});
