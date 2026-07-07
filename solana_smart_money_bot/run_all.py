from __future__ import annotations

import asyncio
import os
import signal
import sys
from dataclasses import dataclass

from config import settings
from src.database import SessionLocal
from src.models import Wallet




def cleanup_example_wallets() -> None:
    with SessionLocal() as db:
        stale = db.query(Wallet).filter(Wallet.wallet_address.like("ExampleWallet%")).all()
        if not stale:
            return
        for w in stale:
            db.delete(w)
        db.commit()
        print(f"[supervisor] removed {len(stale)} stale ExampleWallet entries")

@dataclass
class ServiceSpec:
    name: str
    cmd: list[str]
    enabled: bool = True


async def stream_output(prefix: str, stream: asyncio.StreamReader) -> None:
    while True:
        line = await stream.readline()
        if not line:
            break
        print(f"[{prefix}] {line.decode(errors='replace').rstrip()}", flush=True)


async def run_service(spec: ServiceSpec) -> None:
    if not spec.enabled:
        print(f"[supervisor] {spec.name} disabled")
        return

    while True:
        print(f"[supervisor] starting {spec.name}: {' '.join(spec.cmd)}")
        proc = await asyncio.create_subprocess_exec(
            *spec.cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.getcwd(),
        )

        assert proc.stdout is not None
        assert proc.stderr is not None
        out_task = asyncio.create_task(stream_output(spec.name, proc.stdout))
        err_task = asyncio.create_task(stream_output(spec.name, proc.stderr))

        rc = await proc.wait()
        await out_task
        await err_task

        print(f"[supervisor] {spec.name} exited rc={rc}; restarting in 3s")
        await asyncio.sleep(3)


async def main() -> None:
    python = sys.executable
    cleanup_example_wallets()
    services = [
        ServiceSpec(name="bot", cmd=[python, "main.py"], enabled=True),
        ServiceSpec(
            name="dashboard",
            cmd=[python, "-m", "uvicorn", "dashboard:app", "--host", settings.DASHBOARD_HOST, "--port", str(settings.DASHBOARD_PORT)],
            enabled=settings.ENABLE_DASHBOARD,
        ),
        ServiceSpec(
            name="telegram",
            cmd=[python, "telegram_bot.py"],
            enabled=bool(settings.TELEGRAM_BOT_TOKEN) and settings.ENABLE_TELEGRAM_SERVICE,
        ),
    ]

    tasks = [asyncio.create_task(run_service(s)) for s in services]

    stop = asyncio.Event()

    def _stop_handler(*_: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _stop_handler)

    await stop.wait()
    print("[supervisor] shutdown requested; cancelling services")
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
