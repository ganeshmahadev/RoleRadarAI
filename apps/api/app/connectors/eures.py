"""EURES discovery connector (PRD §8, §9).

Builds company search URLs for the human workflow only. It never retrieves or
extracts EURES vacancy content; an authorized connector can replace it later.
"""

from app.connectors.base import ExternalJob, NormalizedJob
from app.connectors.errors import UnsupportedOperation
from app.models import Company
from app.services.company_normalization import build_eures_search_url

_REFUSAL = "EURES vacancy content is not retrieved; open the search in your browser instead"


class EuresDiscoveryConnector:
    name = "eures_discovery"

    def search_url(self, company: Company) -> str:
        return build_eures_search_url(company.company_name)

    def can_handle_url(self, url: str) -> bool:
        return False

    async def fetch_job_by_url(self, url: str) -> ExternalJob:
        raise UnsupportedOperation(_REFUSAL)

    async def search_company(self, company: Company) -> list[ExternalJob]:
        raise UnsupportedOperation(_REFUSAL)

    async def fetch_job(self, external_id: str) -> ExternalJob:
        raise UnsupportedOperation(_REFUSAL)

    async def normalize_job(self, external_job: ExternalJob) -> NormalizedJob:
        raise UnsupportedOperation(_REFUSAL)
