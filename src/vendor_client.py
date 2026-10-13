from __future__ import annotations

import os
import time
from dataclasses import dataclass
from urllib.parse import quote

import requests

_sleep = time.sleep  # indirection so tests can skip the retry delay without patching the global time module

REQUIRED_RISK_FIELDS = {
    "risk_level": str,
    "security_review_status": str,
    "processes_personal_data": bool,
    "stores_data_outside_region": bool,
}


def get_vendor_risk(vendor_name: str, timeout_seconds: float = 3.0) -> dict:
    """Low-level API client (starter signature, kept for compatibility).

    Raises ``requests.HTTPError`` / ``requests.RequestException`` with the HTTP
    status and the service's own error text preserved.
    """
    base_url = os.getenv("VENDOR_RISK_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
    url = f"{base_url}/vendor-risk/{quote(vendor_name, safe='')}"
    try:
        response = requests.get(url, timeout=timeout_seconds)
        response.raise_for_status()
    except requests.HTTPError as exc:
        response = exc.response
        detail = None
        if response is not None:
            try:
                detail = response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None
        status = f"HTTP {response.status_code}" if response is not None else "HTTP error"
        error = requests.HTTPError(f"{status}: {detail or exc}", response=response)
        raise error from exc
    except requests.RequestException as exc:
        raise requests.RequestException(f"Vendor-risk service unreachable: {exc}") from exc
    return response.json()


@dataclass
class VendorRiskResult:
    """Outcome of one vendor-risk lookup, with outage and absence kept distinct.

    status:
      ok          - a well-formed record was returned
      not_found   - the service answered 404: no record exists (evidence is *missing*)
      unavailable - 5xx, timeout, connection failure, or malformed body (evidence is *unavailable*)
    """

    status: str
    data: dict | None = None
    http_status: int | None = None
    error: str | None = None
    attempts: int = 1
    timed_out: bool = False


def _validate_record(data: object) -> str | None:
    if not isinstance(data, dict):
        return "response body is not a JSON object"
    for name, kind in REQUIRED_RISK_FIELDS.items():
        if not isinstance(data.get(name), kind):
            return f"field '{name}' missing or not {kind.__name__}"
    review_date = data.get("last_review_date")
    if review_date is not None and not isinstance(review_date, str):
        return "field 'last_review_date' is not a string or null"
    return None


def fetch_vendor_risk(vendor_name: str, timeout_seconds: float = 3.0, max_attempts: int = 2) -> VendorRiskResult:
    """Fetch vendor risk, retrying once on transient failures (5xx, timeout, connection error)."""
    last = VendorRiskResult(status="unavailable", error="no attempt made", attempts=0)
    for attempt in range(1, max_attempts + 1):
        try:
            data = get_vendor_risk(vendor_name, timeout_seconds=timeout_seconds)
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else None
            if code == 404:
                return VendorRiskResult("not_found", http_status=404, error=str(exc), attempts=attempt)
            last = VendorRiskResult("unavailable", http_status=code, error=str(exc), attempts=attempt)
            if code is not None and code < 500:
                return last  # client errors are not transient
        except requests.Timeout as exc:
            last = VendorRiskResult("unavailable", error=f"Vendor-risk service timed out: {exc}", attempts=attempt, timed_out=True)
        except requests.RequestException as exc:
            last = VendorRiskResult("unavailable", error=str(exc), attempts=attempt)
        except ValueError as exc:  # body was not JSON
            last = VendorRiskResult("unavailable", error=f"Vendor-risk response was not valid JSON: {exc}", attempts=attempt)
        else:
            problem = _validate_record(data)
            if problem:
                return VendorRiskResult("unavailable", error=f"Malformed vendor-risk record: {problem}", attempts=attempt)
            return VendorRiskResult("ok", data=data, http_status=200, attempts=attempt)
        if attempt < max_attempts:
            _sleep(0.2)
    return last
