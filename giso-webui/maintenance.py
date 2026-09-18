import os
import time

from app import enforce_archive_policy

INTERVAL_SECONDS = int(os.environ.get("ARCHIVE_CLEANUP_INTERVAL_SECONDS", "3600"))
if INTERVAL_SECONDS < 60:
    raise RuntimeError("ARCHIVE_CLEANUP_INTERVAL_SECONDS must be at least 60")


def main() -> None:
    print(
        f"Archive maintenance started; interval_seconds={INTERVAL_SECONDS}", flush=True
    )
    while True:
        try:
            removed = enforce_archive_policy()
        except OSError as exc:
            # A transient filesystem issue (permission hiccup, disk pressure, a
            # flaky network volume) must not crash this daemon: read_only,
            # cap_drop: ALL and healthcheck: disable: true in compose.yaml mean
            # a crash-loop here would silently stop archive retention/quota
            # enforcement with no external signal - skip this cycle and retry
            # on the next interval instead.
            print(
                f"Archive policy check failed, will retry next interval: {exc}",
                flush=True,
            )
        else:
            if removed:
                print(
                    f"Archive policy removed {len(removed)} expired or over-quota job(s)",
                    flush=True,
                )
            else:
                print("Archive policy checked; no files removed", flush=True)
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
