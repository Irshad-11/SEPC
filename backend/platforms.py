"""
platforms.py - Codeforces / LeetCode / CodeChef fetchers
=========================================================
Every fetcher returns:
    {"solved": int, "rating": number or None, "rank": str, "avatar": url or None}
and raises NotFound (wrong username) or FetchError (with a readable reason).

Quick test from a terminal:
    python platforms.py codeforces tourist
    python platforms.py leetcode lee215
    python platforms.py codechef gennady.korotkevich

PythonAnywhere (free account) note:
    Outgoing requests go through a proxy that only allows some sites.
    codeforces.com and alfa-leetcode-api.onrender.com are allowed,
    leetcode.com and codechef.com are NOT. So on PythonAnywhere LeetCode uses
    the alfa API first, and CodeChef must come from local_sync.py.
"""

import gzip
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request

try:  # optional: browser-like TLS, helps with Cloudflare (leetcode.com, codechef.com)
    from curl_cffi import requests as curl_requests
except Exception:  # not installed -> plain urllib is used
    curl_requests = None

ON_PYTHONANYWHERE = bool(os.getenv("PYTHONANYWHERE_DOMAIN") or os.getenv("PYTHONANYWHERE_SITE"))
TIMEOUT = 20
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


class NotFound(Exception):
    pass


class FetchError(Exception):
    pass


def explain(exc):
    """Turn low-level network errors into a sentence a human understands."""
    text = str(exc)
    low = text.lower()
    if ("tunnel" in low and "403" in low) or "connect tunnel failed" in low:
        if ON_PYTHONANYWHERE:
            return "Blocked by PythonAnywhere proxy (site not on free-account allowlist) - use local_sync.py"
        return "Blocked by a network proxy (HTTP 403 on CONNECT)"
    if "timed out" in low or "timeout" in low:
        return f"Timed out after {TIMEOUT}s"
    if "name or service not known" in low or "could not resolve" in low or "getaddrinfo" in low:
        return "DNS error (no internet?)"
    if "connection refused" in low:
        return "Connection refused"
    return text[:200]


def _proxies():
    proxy = os.getenv("https_proxy") or os.getenv("HTTPS_PROXY") or os.getenv("http_proxy") or os.getenv("HTTP_PROXY")
    return {"http": proxy, "https": proxy} if proxy else None


def http(url, method="GET", body=None, headers=None, browser=False):
    """
    Returns (status_code, text). Raises FetchError for network problems.
    browser=True -> use curl_cffi (Chrome fingerprint) when it is installed.
    urllib automatically uses the http_proxy/https_proxy env vars (PythonAnywhere sets them).
    """
    headers = {"User-Agent": UA, "Accept": "*/*", **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    try:
        if browser and curl_requests is not None:
            r = curl_requests.request(method, url, data=data, headers=headers, impersonate="chrome",
                                      timeout=TIMEOUT, proxies=_proxies())
            return r.status_code, r.text
        req = urllib.request.Request(url, data=data, method=method, headers={**headers, "Accept-Encoding": "gzip"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return resp.status, raw.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            raw = e.read()
            if e.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return e.code, raw.decode("utf-8", "replace")
    except Exception as e:
        raise FetchError(explain(e)) from e


def get_json(url, **kw):
    status, text = http(url, **kw)
    try:
        return status, json.loads(text)
    except ValueError:
        raise FetchError(f"HTTP {status}: not JSON ({text[:80].strip()!r})")


# ---------------------------------------------------------------- Codeforces
_cf_lock = threading.Lock()
_cf_last = [0.0]


def _cf_call(url):
    with _cf_lock:  # Codeforces allows ~1 request / 2 seconds
        wait = 2.1 - (time.time() - _cf_last[0])
        if wait > 0:
            time.sleep(wait)
        _cf_last[0] = time.time()
    status, data = get_json(url)
    if data.get("status") != "OK":
        comment = data.get("comment", f"HTTP {status}")
        if "not found" in comment.lower():
            raise NotFound(comment)
        raise FetchError(f"Codeforces: {comment}")
    return data["result"]


def codeforces(username):
    info = _cf_call(f"https://codeforces.com/api/user.info?handles={username}")[0]
    subs = _cf_call(f"https://codeforces.com/api/user.status?handle={username}")
    solved = {
        f"{s['problem'].get('contestId')}-{s['problem'].get('index')}"
        for s in subs
        if s.get("verdict") == "OK" and s.get("problem", {}).get("index")
    }
    avatar = info.get("titlePhoto") or ""
    if "no-title" in avatar:
        avatar = ""
    return {"solved": len(solved), "rating": info.get("rating"),
            "rank": (info.get("rank") or "unrated").title(), "avatar": avatar or None}


# ---------------------------------------------------------------- LeetCode
_LC_QUERY = """query p($username: String!) {
  matchedUser(username: $username) {
    profile { userAvatar }
    submitStatsGlobal { acSubmissionNum { difficulty count } }
  }
  userContestRanking(username: $username) { rating badge { name } }
}"""


def _lc_graphql(username):
    status, text = http("https://leetcode.com/graphql", method="POST", browser=True,
                        body={"query": _LC_QUERY, "variables": {"username": username}},
                        headers={"Referer": f"https://leetcode.com/u/{username}/", "Origin": "https://leetcode.com"})
    try:
        body = json.loads(text)
    except ValueError:
        raise FetchError(f"leetcode.com HTTP {status} (not JSON)")
    data = body.get("data") or {}
    user = data.get("matchedUser")
    if not user:
        errors = " ".join(e.get("message", "") for e in body.get("errors") or [])
        if status == 200 and (not errors or "not exist" in errors.lower()):
            raise NotFound(username)
        raise FetchError(f"leetcode.com: {errors or 'HTTP ' + str(status)}")
    ac = user["submitStatsGlobal"]["acSubmissionNum"]
    contest = data.get("userContestRanking") or {}
    rating = round(contest["rating"]) if contest.get("rating") else None
    return {"solved": next((i["count"] for i in ac if i["difficulty"] == "All"), 0), "rating": rating,
            "rank": ((contest.get("badge") or {}).get("name") or ("Contestant" if rating else "Unrated")),
            "avatar": (user.get("profile") or {}).get("userAvatar")}


def _lc_alfa(username):
    base = f"https://alfa-leetcode-api.onrender.com/{username}"
    status, data = get_json(f"{base}/solved")
    if status == 429:
        raise FetchError("alfa-leetcode-api rate limit hit, try later")
    if isinstance(data, dict) and data.get("errors"):
        raise NotFound(username)
    solved = data.get("solvedProblem") if isinstance(data, dict) else None
    if solved is None:
        msg = str(data.get("message") or data.get("error") or f"HTTP {status}") if isinstance(data, dict) else ""
        if "not exist" in msg.lower() or "not found" in msg.lower():
            raise NotFound(username)
        raise FetchError(f"alfa-leetcode-api: {msg or 'no data'}")
    rating = None
    try:
        _, c = get_json(f"{base}/contest")
        if isinstance(c, dict) and c.get("contestRating"):
            rating = round(c["contestRating"])
    except Exception:
        pass
    return {"solved": int(solved), "rating": rating, "rank": "Contestant" if rating else "Unrated", "avatar": None}


def leetcode(username):
    sources = [_lc_alfa, _lc_graphql] if ON_PYTHONANYWHERE else [_lc_graphql, _lc_alfa]
    reasons = []
    for source in sources:
        try:
            return source(username)
        except NotFound:
            raise
        except FetchError as e:
            reasons.append(str(e))
    raise FetchError(" | ".join(dict.fromkeys(reasons)))


# ---------------------------------------------------------------- CodeChef
def _cc_stars(rating):
    for limit, stars in ((2500, "7★"), (2200, "6★"), (2000, "5★"), (1800, "4★"), (1600, "3★"), (1400, "2★")):
        if rating >= limit:
            return stars
    return "1★"


def codechef(username):
    status, html = http(f"https://www.codechef.com/users/{username}", browser=True,
                        headers={"Referer": "https://www.codechef.com/"})
    if status == 404 or "Could not find page you were looking for" in html:
        raise NotFound(username)
    if status != 200:
        raise FetchError(f"codechef.com HTTP {status}")
    m = re.search(r"Total Problems Solved:\s*(\d+)", html)
    if not m:
        raise FetchError("codechef.com page changed (solved count not found)")
    r = re.search(r'class="rating-number"[^>]*>\s*(\d+)', html)
    rating = int(r.group(1)) if r else None
    return {"solved": int(m.group(1)), "rating": rating,
            "rank": _cc_stars(rating) if rating else "Unrated", "avatar": None}


FETCHERS = {"codeforces": codeforces, "leetcode": leetcode, "codechef": codechef}


def fetch(platform, username):
    """One call with one retry. Returns (result, None) or (None, reason)."""
    reason = "unknown error"
    for attempt in (1, 2):
        try:
            result = FETCHERS[platform](username.strip())
            if not isinstance(result.get("solved"), int):
                raise FetchError("no solved count")
            return result, None
        except NotFound:
            return None, "Username not found"
        except FetchError as e:
            reason = str(e)
        except Exception as e:  # site changed shape etc.
            reason = f"{type(e).__name__}: {explain(e)}"
        if "proxy" in reason.lower():
            break  # retrying a blocked site never helps
        time.sleep(1.5)
    return None, reason


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in FETCHERS:
        print("usage: python platforms.py codeforces|leetcode|codechef USERNAME")
        sys.exit(1)
    started = time.time()
    print(fetch(sys.argv[1], sys.argv[2]), f"({time.time() - started:.1f}s)")
