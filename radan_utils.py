from __future__ import annotations

from typing import Any

try:
    from .radan_models import (
        _RASTER_IMAGE_EXTENSIONS,
        _SYMBOL_EXTENSIONS,
        RadanReportResult,
    )
except ImportError:
    from radan_models import _RASTER_IMAGE_EXTENSIONS, _SYMBOL_EXTENSIONS, RadanReportResult


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _coerce_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return bool(value)


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _parse_report_result(value: Any) -> RadanReportResult:
    if isinstance(value, (list, tuple)):
        ok = _coerce_bool(value[0]) if len(value) >= 1 else None
        error_message = _coerce_str(value[1]) if len(value) >= 2 else None
        return RadanReportResult(ok=ok, error_message=error_message)
    return RadanReportResult(ok=_coerce_bool(value), error_message=None)


def _contains_case_insensitive(value: str | None, needle: str | None) -> bool:
    if not needle:
        return True
    if not value:
        return False
    return needle.lower() in value.lower()


def _infer_editor_mode(window_title: str | None) -> str | None:
    if not window_title:
        return None
    lowered = window_title.lower()
    if "part editor" in lowered:
        return "part"
    if "nest editor" in lowered:
        return "nest"
    if "drawing editor" in lowered:
        return "drawing"
    if "symbol editor" in lowered:
        return "symbol"
    return None


def _infer_document_kind_from_path(path: str) -> str:
    extension = path.lower()
    extension = extension[extension.rfind(".") :] if "." in extension else ""
    if extension in _SYMBOL_EXTENSIONS:
        return "symbol"
    if extension in _RASTER_IMAGE_EXTENSIONS:
        return "symbol_from_raster"
    return "drawing"
