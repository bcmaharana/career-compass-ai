"""Adzuna-backed job listings provider (Phase 6).

Plain httpx adapter, no official SDK — same shape as
app/adapters/quotes/zen_quotes_provider.py and
app/adapters/ai_providers/ollama_provider.py: one class, one async
method, httpx.AsyncClient, distinct except branches for a timeout vs.
any other HTTP error, both raising a CareerCompassError subclass.

Country is hardcoded to "us" (this app's real usage is US-based) rather
than a Settings field — no need to build out country selection for a
single-country deployment.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.core.config import Settings
from app.core.exceptions import CareerCompassError
from app.domain.opportunity_intelligence.entities import JobListing

_COUNTRY = "us"


class AdzunaJobProviderError(CareerCompassError):
    code = "JOB_PROVIDER_ERROR"


class AdzunaJobProvider:
    def __init__(self, settings: Settings) -> None:
        self._app_id = settings.adzuna_app_id
        self._app_key = settings.adzuna_app_key
        self._base_url = settings.adzuna_base_url

    async def search(
        self,
        *,
        what: str,
        where: str | None,
        results_per_page: int = 20,
        max_days_old: int | None = None,
        distance_miles: int | None = None,
        employment_time: str | None = None,
        employment_type: str | None = None,
    ) -> list[JobListing]:
        params: dict[str, str | int] = {
            "app_id": self._app_id,
            "app_key": self._app_key,
            "results_per_page": results_per_page,
            "what": what,
        }
        if where:
            params["where"] = where
        if max_days_old:
            params["max_days_old"] = max_days_old
        if distance_miles:
            params["distance"] = distance_miles
        # employment_time/employment_type map straight onto Adzuna's own
        # param names ("full_time"/"part_time", "contract"/"permanent")
        # — confirmed live these are mutually exclusive per facet
        # (combining full_time=1&part_time=1 in one request is a hard
        # 400, not an OR filter), which is exactly why Settings > Job
        # Search Preference exposes these as single-select radios, not
        # checkboxes.
        if employment_time:
            params[employment_time] = 1
        if employment_type:
            params[employment_type] = 1

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self._base_url}/{_COUNTRY}/search/1", params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise AdzunaJobProviderError(
                f"Adzuna didn't respond in time: {exc}", code="JOB_PROVIDER_TIMEOUT"
            ) from exc
        except httpx.HTTPError as exc:
            raise AdzunaJobProviderError(f"Adzuna request failed: {exc}") from exc

        return [_to_job_listing(result) for result in payload.get("results", [])]


def _to_job_listing(result: dict[str, object]) -> JobListing:
    company = result.get("company")
    location = result.get("location")
    salary_min = result.get("salary_min")
    salary_max = result.get("salary_max")
    category = result.get("category")
    created = result.get("created")

    posted_at: datetime | None = None
    if isinstance(created, str):
        try:
            posted_at = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            posted_at = None

    contract_type = result.get("contract_type")
    return JobListing(
        provider_id=str(result.get("id", "")),
        title=str(result.get("title", "")),
        company=(company or {}).get("display_name") if isinstance(company, dict) else None,
        location=(location or {}).get("display_name") if isinstance(location, dict) else None,
        description=str(result.get("description", "")),
        redirect_url=str(result.get("redirect_url", "")),
        salary_min=float(salary_min) if isinstance(salary_min, int | float) else None,
        salary_max=float(salary_max) if isinstance(salary_max, int | float) else None,
        contract_type=contract_type if isinstance(contract_type, str) else None,
        category=(category or {}).get("label") if isinstance(category, dict) else None,
        posted_at=posted_at,
    )
