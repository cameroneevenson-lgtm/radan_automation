from __future__ import annotations

from dataclasses import dataclass

DEFAULT_RADRAFT_PROG_ID = "Radraft.Application"
DEFAULT_RASTER_TO_VECTOR_PROG_ID = "Radan.RasterToVector"
_SYMBOL_EXTENSIONS = {".sym"}
_RASTER_IMAGE_EXTENSIONS = {".bmp", ".dib", ".gif", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}


class RadanComError(RuntimeError):
    """Base error for RADAN COM wrapper failures."""


class RadanComUnavailableError(RadanComError):
    """Raised when no usable COM backend is available."""


class RadanComProtocolError(RadanComError):
    """Raised when the PowerShell bridge returns malformed output."""


class RadanTargetMismatchError(RadanComError):
    """Raised when the attached live RADAN session is not the expected one."""


@dataclass(frozen=True)
class RadanApplicationInfo:
    prog_id: str
    backend: str
    name: str | None
    full_name: str | None
    path: str | None
    software_version: str | None
    process_id: int | None
    visible: bool | None
    interactive: bool | None
    gui_state: int | None
    gui_sub_state: int | None


@dataclass(frozen=True)
class RadanDocumentInfo:
    document_type: int | None
    dirty: bool | None


@dataclass(frozen=True)
class RadanLicenseInfo:
    holder: str | None
    servercode: str | None


@dataclass(frozen=True)
class RadanReportResult:
    ok: bool | None
    error_message: str | None


@dataclass(frozen=True)
class RadanBounds:
    left: float
    bottom: float
    right: float
    top: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.top - self.bottom

    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2.0

    @property
    def center_y(self) -> float:
        return (self.bottom + self.top) / 2.0


@dataclass(frozen=True)
class RadanLiveSessionInfo:
    application: RadanApplicationInfo
    window_title: str | None
    editor_mode: str | None
    pattern: str | None
    bounds: RadanBounds | None

    @property
    def process_id(self) -> int | None:
        return self.application.process_id

    @property
    def visible(self) -> bool | None:
        return self.application.visible

    @property
    def interactive(self) -> bool | None:
        return self.application.interactive


@dataclass(frozen=True)
class RadanRectangleResult:
    session: RadanLiveSessionInfo
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class RadanVisibleSessionInfo:
    process_id: int
    window_title: str
    editor_mode: str | None
