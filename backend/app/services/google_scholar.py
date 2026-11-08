from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx


SERPAPI_SEARCH_URL = "https://serpapi.com/search"
SERPAPI_PROVIDER = "serpapi_google_scholar_author"


class GoogleScholarError(RuntimeError):
    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


class GoogleScholarService:
    def __init__(self, api_key: str, *, timeout: float = 30.0):
        self._api_key = api_key
        self._timeout = timeout

    def fetch_profile(
        self,
        scholar_id: str | None,
        *,
        scholar_url: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> dict[str, Any]:
        if not scholar_id:
            raise GoogleScholarError("missing_scholar_id")
        if not self._api_key:
            raise GoogleScholarError("missing_api_key")

        try:
            with httpx.Client(timeout=self._timeout, transport=transport) as client:
                response = client.get(
                    SERPAPI_SEARCH_URL,
                    params={
                        "engine": "google_scholar_author",
                        "author_id": scholar_id,
                        "api_key": self._api_key,
                        "hl": "en",
                    },
                )
        except httpx.TimeoutException:
            raise GoogleScholarError("provider_timeout") from None
        except httpx.HTTPError:
            raise GoogleScholarError("provider_http_error") from None

        if response.is_error:
            raise GoogleScholarError("provider_http_error")
        try:
            payload = response.json()
        except ValueError:
            raise GoogleScholarError("invalid_provider_response") from None
        if not isinstance(payload, dict):
            raise GoogleScholarError("invalid_provider_response")
        if payload.get("error"):
            raise GoogleScholarError("provider_error")

        author = payload.get("author")
        if not isinstance(author, dict):
            raise GoogleScholarError("missing_author")

        search_parameters = payload.get("search_parameters")
        primary_id = (
            _identity_value(search_parameters.get("author_id"))
            if isinstance(search_parameters, dict)
            else None
        )
        nested_ids = [
            value
            for key in ("author_id", "scholar_id", "id")
            if (value := _identity_value(author.get(key))) is not None
        ]

        search_metadata = payload.get("search_metadata")
        metadata_url = (
            search_metadata.get("google_scholar_author_url")
            if isinstance(search_metadata, dict)
            else None
        )
        metadata_url = metadata_url if isinstance(metadata_url, str) and metadata_url else None
        nested_urls = [
            author[key]
            for key in ("scholar_url", "link", "url")
            if isinstance(author.get(key), str) and author[key]
        ]
        provider_urls = ([metadata_url] if metadata_url else []) + nested_urls
        provider_url_ids = [_scholar_id_from_url(url) for url in provider_urls]

        if metadata_url and provider_url_ids[0] is None:
            raise GoogleScholarError("identity_unverified")
        if any(url_id is not None for url_id in provider_url_ids):
            provider_url_ids = [url_id for url_id in provider_url_ids if url_id is not None]

        provider_ids = ([primary_id] if primary_id else []) + nested_ids
        returned_id = primary_id or (nested_ids[0] if nested_ids else None)
        if returned_id is None and provider_url_ids:
            returned_id = provider_url_ids[0]
        if returned_id is None:
            raise GoogleScholarError("identity_unverified")

        if any(value != returned_id for value in provider_ids + provider_url_ids):
            raise GoogleScholarError("identity_unverified")
        if returned_id != scholar_id:
            raise GoogleScholarError("identity_unverified")

        stored_url_id = _scholar_id_from_url(scholar_url)
        if stored_url_id is not None and stored_url_id != returned_id:
            raise GoogleScholarError("identity_unverified")
        author_url = metadata_url or (nested_urls[0] if nested_urls else None)

        try:
            citations = _citation_metrics(payload.get("cited_by"))
            publications = _publications(payload.get("articles"))
        except (TypeError, ValueError):
            raise GoogleScholarError("malformed_citation_metrics") from None

        return {
            "scholar_id": returned_id,
            "scholar_url": author_url or scholar_url,
            "scholar_name": author.get("name"),
            **citations,
            "publications": publications,
            "source": SERPAPI_PROVIDER,
            "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }


def _identity_value(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _scholar_id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    query = parse_qs(urlparse(url).query)
    for key in ("user", "author_id", "scholar_id"):
        value = query.get(key)
        if value:
            return value[0]
    return None


def _integer_metric(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("invalid integer metric")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        normalized = value.strip().replace(",", "")
        if not normalized.isdigit():
            raise ValueError("invalid integer metric")
        parsed = int(normalized)
    else:
        raise ValueError("invalid integer metric")
    if parsed < 0:
        raise ValueError("negative integer metric")
    return parsed


def _citation_metrics(cited_by: Any) -> dict[str, int | None]:
    names = {
        "citations": ("total_citations", "citations_since_2016"),
        "h_index": ("h_index", "h_index_since_2016"),
        "i10_index": ("i10_index", "i10_index_since_2016"),
    }
    result: dict[str, int | None] = {
        output: None for outputs in names.values() for output in outputs
    }
    if cited_by is None:
        return result
    if not isinstance(cited_by, dict):
        raise ValueError("invalid citation section")
    table = cited_by.get("table")
    if table is None:
        return result
    if not isinstance(table, list):
        raise ValueError("invalid citation table")
    for row in table:
        if not isinstance(row, dict):
            raise ValueError("invalid citation row")
        for source, outputs in names.items():
            values = row.get(source)
            if values is None:
                continue
            if not isinstance(values, dict):
                raise ValueError("invalid citation metric")
            result[outputs[0]] = _integer_metric(values.get("all"))
            result[outputs[1]] = _integer_metric(values.get("since_2016"))
    return result


def _publications(articles: Any) -> list[dict[str, Any]]:
    if articles is None:
        return []
    if not isinstance(articles, list):
        raise ValueError("invalid articles")
    output = []
    for article in articles:
        if not isinstance(article, dict):
            raise ValueError("invalid article")
        authors = article.get("authors")
        if isinstance(authors, str):
            authors = [authors] if authors else []
        elif not isinstance(authors, list):
            authors = []
        cited_by = article.get("cited_by")
        if isinstance(cited_by, dict):
            citation_count = _integer_metric(cited_by.get("value"))
        else:
            citation_count = _integer_metric(cited_by)
        year = _integer_metric(article.get("year"))
        output.append(
            {
                "title": article.get("title"),
                "authors": authors,
                "publication": article.get("publication"),
                "year": year,
                "citation_count": citation_count,
                "link": article.get("link"),
                "citation_id": article.get("citation_id"),
            }
        )
    return output