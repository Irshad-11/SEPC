"""
local_sync.py - fetch on YOUR computer, push to the server (PythonAnywhere)
===========================================================================
Use it when the server cannot reach a site (CodeChef, beecrowd, sometimes LeetCode).

    python local_sync.py                       all platforms (codeforces, leetcode, codechef, beecrowd)
    python local_sync.py codechef beecrowd     only these
    python local_sync.py --daily 23:30         stay open and run every day at 23:30 (Dhaka/PC time)

Needs in backend/.env : BACKEND_URL and INGEST_SECRET (same secret as the server's .env).
Beecrowd needs Playwright + Brave/Chrome (see doc/README.md). Other platforms need nothing extra.

Flow:
    1. GET  {BACKEND_URL}/api/ingest/accounts        -> usernames of every platform
    2. fetch each username here (platforms.py / beecrowd.py)
    3. POST {BACKEND_URL}/api/ingest/<platform>      -> server saves today's numbers
Requests are signed with HMAC(INGEST_SECRET), the secret itself never travels.
"""

import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))

import platforms  # noqa: E402

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000").rstrip("/")
SECRET = os.getenv("INGEST_SECRET", "")
ALL = ["codeforces", "leetcode", "codechef", "beecrowd"]


def call(method, path, payload=None):
    body = json.dumps(payload).encode() if payload is not None else b""
    ts = str(int(time.time()))
    sig = hmac.new(SECRET.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(BACKEND_URL + path, data=body if method == "POST" else None, method=method,
                                 headers={"Content-Type": "application/json", "X-Timestamp": ts,
                                          "X-Signature": sig, "User-Agent": "sepc-local-sync"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Server said {e.code}: {e.read().decode(errors='replace')[:300]}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Cannot reach {BACKEND_URL}: {e.reason}")


def fetch_platform(platform, usernames):
    users = {}
    if platform == "beecrowd":
        try:
            import beecrowd
        except ImportError:
            print("  beecrowd skipped: run  pip install playwright  first")
            return users
        for uid, stats in beecrowd.get_beecrowd_bulk(usernames).items():
            users[uid] = stats  # {"rank", "points", "submissions", "solved"} ("Error"/"Not Found" on failure)
        return users
    for i, name in enumerate(usernames, 1):
        t0 = time.time()
        result, reason = platforms.fetch(platform, name)
        users[name] = result or {"solved": None, "error": reason}
        status = f"{result['solved']} solved" if result else f"ERROR {reason}"
        print(f"  [{i}/{len(usernames)}] {name:<24} {status} ({time.time() - t0:.1f}s)")
    return users


def run_once(selected):
    if not SECRET:
        raise SystemExit("INGEST_SECRET missing in backend/.env")
    print(f"Server: {BACKEND_URL}")
    accounts = call("GET", "/api/ingest/accounts")
    for platform in selected:
        names = accounts.get(platform, [])
        print(f"\n{platform}: {len(names)} accounts")
        if not names:
            continue
        users = fetch_platform(platform, names)
        if users:
            answer = call("POST", f"/api/ingest/{platform}", {"users": users})
            print(f"  pushed -> ok {answer['ok']}, failed {answer['failed']}, unknown {len(answer['unknown'])}")


def main(args):
    daily = None
    if "--daily" in args:
        i = args.index("--daily")
        daily = args[i + 1] if i + 1 < len(args) else "23:30"
        args = args[:i] + args[i + 2:]
    selected = [a for a in args if a in ALL] or ALL
    if not daily:
        run_once(selected)
        return
    hour, minute = (int(x) for x in daily.split(":"))
    print(f"Daily mode: runs every day at {daily}. Keep this window open (Ctrl+C to stop).")
    while True:
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        print(f"Next run: {target:%Y-%m-%d %H:%M}")
        while datetime.now() < target:
            time.sleep(30)
        try:
            run_once(selected)
        except SystemExit as e:
            print(f"Run failed: {e}")


if __name__ == "__main__":
    main(sys.argv[1:])
