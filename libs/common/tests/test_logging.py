import json
import logging

from lily_common.logging import JsonFormatter, bind_context, session_id_var, trace_id_var


def format_record(message: str, **extra: str) -> dict[str, object]:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=None,
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    line = JsonFormatter(service="test-svc").format(record)
    parsed: dict[str, object] = json.loads(line)
    return parsed


def test_log_line_shape() -> None:
    payload = format_record("hello")
    assert payload["service"] == "test-svc"
    assert payload["level"] == "INFO"
    assert payload["message"] == "hello"
    assert "timestamp" in payload
    assert "trace_id" in payload
    assert "session_id" in payload


def test_bound_context_appears_on_log_lines() -> None:
    token_t = trace_id_var.set(None)
    token_s = session_id_var.set(None)
    try:
        bind_context(trace_id="trace-123", session_id="sess-456")
        payload = format_record("with context")
        assert payload["trace_id"] == "trace-123"
        assert payload["session_id"] == "sess-456"
    finally:
        trace_id_var.reset(token_t)
        session_id_var.reset(token_s)


def test_extra_fields_pass_through() -> None:
    payload = format_record("extra", intent="compatibility", graph_node="router")
    assert payload["intent"] == "compatibility"
    assert payload["graph_node"] == "router"
