import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from importlib.resources import files
from ss_contracts.core import Scope
from .core import demo, run_scenario

def load_fixture(path=None):
    return json.loads(Path(path).read_text(encoding="utf-8") if path else files(__package__).joinpath("fixtures/demo.json").read_text(encoding="utf-8"))

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Pinned composition, topology setup and cross-repository verification")
    sub = parser.add_subparsers(dest="mode", required=True)
    demonstration = sub.add_parser("demo")
    demonstration.add_argument("--fixture", type=Path)
    demonstration.add_argument("--state-dir", type=Path)
    live = sub.add_parser("topology")
    live.add_argument("--amqp-url", default=os.environ.get("SS_AMQP_URL", "amqp://guest:guest@127.0.0.1/"))
    live.add_argument("--exchange", default="ss.mre.events")

    live.add_argument("--profile-id", required=True)
    args = parser.parse_args()
    try:
        if args.mode == "demo":
            result = asyncio.run(run_scenario(load_fixture(args.fixture), args.state_dir)) if args.state_dir else demo(load_fixture(args.fixture))
        else:
            result = asyncio.run(run_live(args))
    except (Exception, KeyboardInterrupt) as exc:
        # Never print raw credentials, model prompts or exception text.
        print(json.dumps({"ok": False, "error": type(exc).__name__}), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0

async def run_live(args):
    from .topology import configure
    return await configure(args.amqp_url, args.profile_id, args.exchange)
