"""ERDA API: REST + tiles + SSE memo stream (spec §2).

Serves the terminal UI. All numbers it returns come from the data plane with
provenance attached — the API never computes domain math itself (that lives in
packages/engine) and never fabricates values.
"""

__version__ = "0.1.0"
