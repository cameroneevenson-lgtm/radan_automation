from __future__ import annotations

from radan_com import open_application


def main() -> int:
    with open_application() as app:
        info_before = app.info()
        app.interactive = True
        app.visible = True
        info_after = app.info()

    print("RADAN action complete")
    print(f"backend={info_after.backend}")
    print(f"attached_existing={not app.created_new_instance}")
    print(f"process_id={info_after.process_id}")
    print(f"name={info_after.name}")
    print(f"version={info_after.software_version}")
    print(f"visible_before={info_before.visible}")
    print(f"visible_after={info_after.visible}")
    print("action=Set Visible=True and Interactive=True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
