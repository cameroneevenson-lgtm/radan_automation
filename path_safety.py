from __future__ import annotations

from pathlib import Path, PureWindowsPath


OWNED_INVENTOR_OUTPUT_SUFFIXES = ("_Radan.csv", "_report.txt")


def is_w_drive_path(path: str | Path) -> bool:
    """Return True when a path targets the W: source-geometry drive."""

    text = str(path or "").strip()
    if not text:
        return False
    normalized = text.replace("/", "\\")
    if normalized.startswith("\\\\?\\"):
        normalized = normalized[4:]
    return PureWindowsPath(normalized).drive.casefold() == "w:"


def is_owned_inventor_output(path: str | Path, *, spreadsheet_path: str | Path | None = None) -> bool:
    """Return True for the W-side files created by the Inventor handoff flow."""

    candidate = Path(str(path))
    if spreadsheet_path is not None:
        spreadsheet = Path(str(spreadsheet_path))
        allowed_names = {
            f"{spreadsheet.stem}_Radan.csv".casefold(),
            f"{spreadsheet.stem}_report.txt".casefold(),
        }
        return candidate.name.casefold() in allowed_names
    name = candidate.name.casefold()
    return name.endswith(tuple(suffix.casefold() for suffix in OWNED_INVENTOR_OUTPUT_SUFFIXES))


def assert_w_drive_write_allowed(
    path: str | Path | None,
    *,
    operation: str,
    allow_owned_inventor_output: bool = False,
    spreadsheet_path: str | Path | None = None,
) -> None:
    """Block writes to W: except for explicitly-owned Inventor handoff files."""

    if path is None or not is_w_drive_path(path):
        return
    if allow_owned_inventor_output and is_owned_inventor_output(path, spreadsheet_path=spreadsheet_path):
        return
    exception = " The only allowed W: mutation is moving/deleting Inventor-generated *_Radan.csv and *_report.txt handoff files."
    raise RuntimeError(f"Refusing to {operation} on W: path: {path}.{exception}")
