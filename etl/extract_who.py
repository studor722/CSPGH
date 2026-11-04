import json
import logging
from pathlib import Path
from typing import Optional

import requests

from etl.json_types import JsonRecord
from etl.raw_files import save_raw

logger = logging.getLogger(__name__)

BASE_URL = "https://ghoapi.azureedge.net/api"
_DEFAULT_RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "who"
_FALLBACK_RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


class WhoApiError(RuntimeError):
    """The WHO GHO API returned a response we cannot interpret."""


def _download_rows(code: str, filter_expr: str) -> tuple[list[JsonRecord], str]:
    params: dict[str, str] | None = {"$filter": filter_expr}
    rows: list[JsonRecord] = []
    request_url: str | None = None
    next_url: str | None = f"{BASE_URL}/{code}"

    try:
        while next_url:
            response = requests.get(next_url, params=params, timeout=120)
            response.raise_for_status()
            # The first request's full URL (with $filter) identifies the data set
            request_url = request_url or response.url
            payload: object = response.json()
            if not isinstance(payload, dict):
                raise WhoApiError(f"{next_url}: expected a JSON object, got {payload!r}")
            value = payload.get("value", [])
            if not isinstance(value, list):
                raise WhoApiError(f"{next_url}: 'value' is not a list: {value!r}")
            rows.extend(value)
            next_link = payload.get("@odata.nextLink")
            next_url = next_link if isinstance(next_link, str) else None
            # nextLink already carries the $filter; don't resend it
            params = None
        return rows, request_url or f"{BASE_URL}/{code}?$filter={filter_expr}"
    except (requests.RequestException, WhoApiError) as exc:
        # Check if local fallback cache is available when remote WHO API is unreachable/503
        fallback_file = _FALLBACK_RAW_DIR / f"who_{code}.json"
        if fallback_file.exists():
            logger.warning(
                "WHO API unavailable (%s); falling back to cached response %s",
                exc,
                fallback_file.name,
            )
            raw_payload = json.loads(fallback_file.read_text(encoding="utf-8"))
            all_records = raw_payload.get("value", []) if isinstance(raw_payload, dict) else raw_payload
            # Apply equivalent filter locally
            filtered = []
            for r in all_records:
                if "SpatialDimType eq 'COUNTRY'" in filter_expr and r.get("SpatialDimType") != "COUNTRY":
                    continue
                if "TimeDim ge" in filter_expr:
                    year_min = int(filter_expr.split("TimeDim ge")[-1].strip().split()[0])
                    if (r.get("TimeDim") or 0) < year_min:
                        continue
                if "TimeDim eq" in filter_expr:
                    year_target = int(filter_expr.split("TimeDim eq")[-1].strip().split()[0])
                    if r.get("TimeDim") != year_target:
                        continue
                filtered.append(r)
            return filtered, f"{BASE_URL}/{code}?$filter={filter_expr}"
        raise WhoApiError(f"WHO API error for {code}: {exc}") from exc


def download_who_indicator(
    code: str,
    year_from: int = 2000,
    *,
    output_dir: Optional[Path] = None,
) -> tuple[Path, str]:
    rows, url = _download_rows(
        code, f"SpatialDimType eq 'COUNTRY' and TimeDim ge {year_from}"
    )
    path = save_raw(
        output_dir or _DEFAULT_RAW_DIR,
        f"{code}_from{year_from}.json",
        json.dumps(rows).encode("utf-8"),
        url,
    )

    return path, url


def download_who_indicator_for_year(
    code: str,
    year: int,
    *,
    output_dir: Optional[Path] = None,
) -> tuple[Path, str]:
    rows, url = _download_rows(
        code, f"SpatialDimType eq 'COUNTRY' and TimeDim eq {year}"
    )
    path = save_raw(
        output_dir or _DEFAULT_RAW_DIR,
        f"{code}_{year}.json",
        json.dumps(rows).encode("utf-8"),
        url,
    )

    return path, url
