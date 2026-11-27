import time
from datetime import datetime, timezone
from github_scan import scan_all

INTERVAL_SECONDS = 300  # 5 خولەک


def main() -> None:
    print("Starting Rabaty AI Trader 5-minute loop...")
    while True:
        started_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"--- Scan cycle started at {started_at} ---")
        try:
            scan_all()
        except Exception as e:
            print(f"[Loop Error] {e}")

        print(f"Sleeping for {INTERVAL_SECONDS} seconds...")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()