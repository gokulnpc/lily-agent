"""robots.txt compliance (D12 politeness, NFR-16).

A per-host cache over the stdlib robots parser. The fetch is **injected** so the
production caller wires in the real (Chrome-channel) fetcher while tests pass a
plain string — no network in unit tests.

Failure policy: a missing robots.txt (404) means "allow all" (web convention);
a robots.txt that cannot be retrieved at all (network/5xx) means "disallow" —
fail safe, never crawl a host whose rules we could not read.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Callable, Iterable
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

# Returns the robots.txt body, "" if the host has none (404), or raises on a
# transient failure (network/5xx) the caller should back off and retry.
RobotsFetcher = Callable[[str], str]


class RobotsCache:
    """robots.txt compliance with a per-host cache.

    The stdlib parser does **prefix** matching, which honors every rule in
    PartSelect's `User-agent: *` group (all prefix/exact). It does NOT honor
    mid-path `*` wildcards (e.g. `/Models/*/Parts/`, which on PartSelect appears
    only under named-bot groups). `extra_disallow_globs` closes that gap
    explicitly so we never under-comply on a wildcard rule we care about.
    """

    def __init__(
        self,
        fetcher: RobotsFetcher,
        user_agent: str,
        extra_disallow_globs: Iterable[str] = ("*/Models/*/Parts/*",),
    ) -> None:
        self._fetcher = fetcher
        self._user_agent = user_agent
        self._extra_globs = tuple(extra_disallow_globs)
        self._parsers: dict[str, RobotFileParser] = {}

    @staticmethod
    def _origin(url: str) -> str:
        parts = urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}"

    def _parser_for(self, url: str) -> RobotFileParser:
        origin = self._origin(url)
        parser = self._parsers.get(origin)
        if parser is None:
            body = self._fetcher(f"{origin}/robots.txt")
            parser = RobotFileParser()
            parser.parse(body.splitlines())
            self._parsers[origin] = parser
        return parser

    def allowed(self, url: str) -> bool:
        """Whether our user-agent may fetch this URL per the host's robots.txt."""
        if any(fnmatch.fnmatch(url, glob) for glob in self._extra_globs):
            return False
        return self._parser_for(url).can_fetch(self._user_agent, url)
