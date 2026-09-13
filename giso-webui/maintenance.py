import os
import time

from app import enforce_archive_policy

INTERVAL_SECONDS = int(os.environ.get("ARCHIVE_CLEANUP_INTERVAL_SECONDS", "3600"))
if INTERVAL_SECONDS < 60:
    raise RuntimeError("ARCHIVE_CLEANUP_INTERVAL_SECONDS must be at least 60")


def main() -> None:
    print(f"Archive maintenance started; interval_seconds={INTERVAL_SECONDS}", flush=True)
    while True:
        removed = enforce_archive_policy()
        if removed:
            print(f"Archive policy removed {len(removed)} expired or over-quota job(s)", flush=True)
        else:
            print("Archive policy checked; no files removed", flush=True)
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
