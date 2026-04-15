from __future__ import annotations

from radan_com import RadanComUnavailableError, attach_application


def main() -> int:
    try:
        with attach_application() as app:
            info = app.info()
            print("attached_existing=True")
            print(f"backend={app.backend_name}")
            print(f"created_new={app.created_new_instance}")
            print(f"process_id={info.process_id}")
            print(f"name={info.name}")
            print(f"visible={info.visible}")
            print(f"interactive={info.interactive}")
            return 0
    except RadanComUnavailableError as exc:
        print("attached_existing=False")
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
