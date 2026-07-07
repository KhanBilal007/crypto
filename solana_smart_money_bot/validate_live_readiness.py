from __future__ import annotations

from config import settings


def _bool(v: bool) -> str:
    return "true" if v else "false"


def main() -> None:
    paper_ready = settings.EXECUTION_MODE == "paper" and settings.PAPER_TRADING and not settings.LIVE_TRADING_ENABLED
    forward_ready = settings.FORWARD_TESTING_MODE and settings.EXECUTION_MODE == "paper" and not settings.LIVE_TRADING_ENABLED
    live_ready = False
    tiny_staging_ready = False

    print(f"PAPER_MODE_READY={_bool(paper_ready)}")
    print(f"FORWARD_TESTING_READY={_bool(forward_ready)}")
    print(f"LIVE_TRADING_READY={_bool(live_ready)}")
    print(f"TINY_STAGING_TEST_READY={_bool(tiny_staging_ready)}")


if __name__ == "__main__":
    main()
