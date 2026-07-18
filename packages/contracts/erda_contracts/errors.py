"""Typed failure semantics (spec §0 rule 4): a failing source raises and stops.

No connector may swallow one of these and substitute invented data. The only
sanctioned degradation paths are the ones the spec names explicitly (e.g.
yf_curve falling back to front-month + EIA STEO, labelled indicative).
"""


class ErdaDataError(Exception):
    """Base class for all data-plane failures."""


class SourceUnavailable(ErdaDataError):
    """The upstream endpoint could not be reached or returned an error."""

    def __init__(self, source_id: str, detail: str):
        self.source_id = source_id
        super().__init__(f"[{source_id}] source unavailable: {detail}")


class ContractViolation(ErdaDataError):
    """Fetched data failed its pandera contract — never persisted."""

    def __init__(self, source_id: str, detail: str):
        self.source_id = source_id
        super().__init__(f"[{source_id}] contract violation: {detail}")


class StaleData(ErdaDataError):
    """Data exists but is older than the source's freshness SLA."""

    def __init__(self, source_id: str, detail: str):
        self.source_id = source_id
        super().__init__(f"[{source_id}] stale: {detail}")
