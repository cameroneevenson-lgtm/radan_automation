from __future__ import annotations

from typing import Any

try:
    from .radan_backends import _Backend
    from .radan_models import RadanLicenseInfo, RadanReportResult
    from .radan_utils import _coerce_bool, _coerce_int, _coerce_str, _parse_report_result
except ImportError:
    from radan_backends import _Backend
    from radan_models import RadanLicenseInfo, RadanReportResult
    from radan_utils import _coerce_bool, _coerce_int, _coerce_str, _parse_report_result


class RadanMac:
    def __init__(self, backend: _Backend) -> None:
        self._backend = backend
        self._path = ("Mac",)

    def _get_property(self, name: str) -> Any:
        return self._backend.get_path_property(self._path, name)

    def _call_method(self, name: str, *args: Any) -> Any:
        return self._backend.call_path_method(self._path, name, *args)

    def license_info(self) -> RadanLicenseInfo:
        return RadanLicenseInfo(
            holder=_coerce_str(self._call_method("lic_get_holder")),
            servercode=_coerce_str(self._call_method("lic_get_servercode")),
        )

    def license_available(self, name: str) -> bool | None:
        return _coerce_bool(self._call_method("lic_available", name))

    def license_confirm(self, name: str) -> bool | None:
        return _coerce_bool(self._call_method("lic_confirm", name))

    def license_request(self, name: str) -> bool | None:
        return _coerce_bool(self._call_method("lic_request", name))

    @property
    def prompt_string(self) -> str | None:
        return _coerce_str(self._get_property("PRS"))

    @property
    def part_pattern(self) -> str | None:
        return _coerce_str(self._get_property("PART_PATTERN"))

    @property
    def current_pattern_path(self) -> str | None:
        return _coerce_str(self._get_property("CUP"))

    @property
    def open_pattern_path(self) -> str | None:
        return _coerce_str(self._get_property("COP"))

    def report_type(self, file_type_name: str) -> int | None:
        property_name = f"REPORT_TYPE_{file_type_name.strip().upper()}"
        return _coerce_int(self._get_property(property_name))

    def keystroke(self, command: str) -> int | None:
        return _coerce_int(self._call_method("rfmac", command))

    def profile_healing(
        self,
        pattern: str,
        *,
        include_sub_patterns: bool = False,
        tolerance: float = 0.005,
        realise_ellipses: bool = False,
        remove_small_features: bool = False,
        close_small_gaps: bool = False,
        merge_overlaps: bool = False,
        simplify_data: bool = False,
    ) -> bool | None:
        return _coerce_bool(
            self._call_method(
                "profile_healing",
                pattern,
                bool(include_sub_patterns),
                float(tolerance),
                bool(realise_ellipses),
                bool(remove_small_features),
                bool(close_small_gaps),
                bool(merge_overlaps),
                bool(simplify_data),
            )
        )

    def profile_healing_with_timeout(
        self,
        pattern: str,
        *,
        include_sub_patterns: bool = False,
        tolerance: float = 0.005,
        realise_ellipses: bool = False,
        remove_small_features: bool = False,
        close_small_gaps: bool = False,
        merge_overlaps: bool = False,
        simplify_data: bool = False,
        time_limit: float = 0.0,
    ) -> int | None:
        return _coerce_int(
            self._call_method(
                "profile_healing_with_timeout",
                pattern,
                bool(include_sub_patterns),
                float(tolerance),
                bool(realise_ellipses),
                bool(remove_small_features),
                bool(close_small_gaps),
                bool(merge_overlaps),
                bool(simplify_data),
                float(time_limit),
            )
        )

    def profile_extraction(
        self,
        pattern: str,
        *,
        include_sub_patterns: bool = False,
        delete_by_pen: bool = False,
        pen_mask: int = 0,
        lines_arcs_only: bool = False,
        full_linetype_only: bool = False,
    ) -> bool | None:
        return _coerce_bool(
            self._call_method(
                "profile_extraction",
                pattern,
                bool(include_sub_patterns),
                bool(delete_by_pen),
                int(pen_mask),
                bool(lines_arcs_only),
                bool(full_linetype_only),
            )
        )

    def flat_thumbnail(self, path: str, width: int, height: int) -> bool | None:
        return _coerce_bool(self._call_method("fla_thumbnail", path, int(width), int(height)))

    def model_thumbnail(self, path: str, width: int) -> bool | None:
        return _coerce_bool(self._call_method("mfl_thumbnail", path, int(width)))

    def output_project_report(self, report_name: str, file_path: str, file_type: int) -> RadanReportResult:
        return _parse_report_result(self._call_method("prj_output_report", report_name, file_path, int(file_type), ""))

    def output_setup_report(self, report_name: str, file_path: str, file_type: int) -> RadanReportResult:
        return _parse_report_result(self._call_method("stp_output_report", report_name, file_path, int(file_type), ""))
