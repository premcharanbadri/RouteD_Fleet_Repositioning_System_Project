"""AI layer: natural-language order intake and dispatch briefings.

Every entry point degrades gracefully to a deterministic, rule-based
implementation when no ANTHROPIC_API_KEY is configured (or the API call fails),
so RouteIQ is always fully functional offline.
"""
