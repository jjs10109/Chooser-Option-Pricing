"""Python entry point for data, training and local presentation."""

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(
        description="Market prices -> implied volatility -> ML"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "sample", help="Generate shareable sample and evaluate all models offline"
    )
    refresh = commands.add_parser(
        "refresh", help="Download original APIs through today, then train"
    )
    refresh.add_argument("--start")
    refresh.add_argument(
        "--end", default=datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    )
    refresh.add_argument("--refresh-cache", action="store_true")
    train = commands.add_parser("train", help="Run on existing CSV data")
    train.add_argument("--data", default="data/market")
    train.add_argument("--output", default="reports/market")
    dashboard = commands.add_parser(
        "dashboard", help="Open local presentation app without downloading data"
    )
    dashboard.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()
    if args.command == "dashboard":
        return subprocess.call(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(ROOT / "frontend" / "app.py"),
                "--server.address=127.0.0.1",
                f"--server.port={args.port}",
                "--browser.gatherUsageStats=false",
            ]
        )
    from .pipeline import run

    if args.command == "sample":
        from .sample import make_sample

        folder = make_sample(ROOT / "data" / "sample")
        print(run(folder, ROOT / "reports" / "sample").to_string(index=False))
    elif args.command == "refresh":
        from .collect import collect

        start = (
            args.start
            or (datetime.fromisoformat(args.end) - timedelta(days=42))
            .date()
            .isoformat()
        )
        folder = collect(
            start,
            args.end,
            ROOT / "data" / "market",
            ROOT / "data" / "vendor",
            refresh=args.refresh_cache,
        )
        print(run(folder, ROOT / "reports" / "market").to_string(index=False))
    else:
        print(run(args.data, args.output).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
