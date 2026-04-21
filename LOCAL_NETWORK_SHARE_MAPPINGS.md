# Local Network Share Mappings

This note captures operator-provided Windows drive mappings that are useful for
RADAN automation and file lookup on this machine.

Recorded on: 2026-04-21

## Mappings

- `L:` -> `\\SVRDC\Laser`
- `W:` -> `\\SVRDC\Workshop`

## Notes

- These are user-session mappings. A RADAN desktop session may be able to see
  them even when a non-interactive automation shell cannot.
- When possible, prefer the UNC path in automation logs and scripts so the
  intended share is preserved even if the mapped drive letter is unavailable.
