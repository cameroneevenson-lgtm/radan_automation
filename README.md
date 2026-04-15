# RADAN Automation

Reusable RADAN automation wrapper, probes, and reverse-engineering notes extracted from `radan_kitter`.

## What Lives Here

- `radan_com.py`
  - Python wrapper for `Radraft.Application`
- `radan_com_bridge.ps1`
  - PowerShell bridge backend for COM access
- `inspect_radan_api_xml.py`
  - Search the shipped RADAN XML docs
- `inspect_dotnet_method_il.ps1`
  - Inspect IL for the managed RADAN interop assembly
- `probe_radan_*` and `try_radan_*`
  - Attach, headless, and output probes
- `RADAN_*.md`
  - Findings and quick-reference notes
- `tests/test_radan_com.py`
  - Unit coverage for the wrapper surface
- `docs/Radan API Programming Help.pdf`
  - Local PDF reference copy

## Local References

- PDF: [docs/Radan API Programming Help.pdf](</c:/Tools/radan_automation/docs/Radan API Programming Help.pdf>)
- Installed CHM help:
  - `C:\Program Files\Mazak\Mazak\help\manuals\radanapi.chm`
  - `C:\Program Files\Mazak\Mazak\help\manuals\radraft.chm`

## Setup

Install the automation-only Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run the wrapper tests:

```powershell
python -m unittest tests.test_radan_com
```

## Verified Probes

- `try_radan_headless.py`
- `try_radan_headless_save.py`
- `try_radan_headless_outputs.py`
- `probe_radan_attach.py`
- `probe_radan_managed_attach.ps1`
