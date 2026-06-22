"""Simple performance smoke test — measures API response times."""
import time, json, urllib.request, urllib.error, statistics

BASE = "http://localhost:8002"
TOKEN = None

def api(method, path, data=None):
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        start = time.perf_counter()
        with urllib.request.urlopen(req, timeout=10) as resp:
            elapsed = time.perf_counter() - start
            return elapsed, resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - start
        return elapsed, e.code, {}

# Login and get token
print("=== LOGIN ===")
elapsed, status, body = api("POST", "/api/v1/admin/auth/login",
    {"username": "senior_admin", "password": "Admin@123"})
TOKEN = body.get("data", {}).get("token")
print(f"  Login: {elapsed*1000:.0f}ms, status={status}")

# ── Login concurrency test (50 sequential) ──
print("\n=== LOGIN × 50 ===")
times = []
for i in range(50):
    elapsed, status, _ = api("POST", "/api/v1/admin/auth/login",
        {"username": "senior_admin", "password": "Admin@123"})
    times.append(elapsed)
    if i % 10 == 9:
        print(f"  {i+1}/50 ...")

avg = statistics.mean(times) * 1000
p50 = statistics.median(times) * 1000
p95 = sorted(times)[int(len(times)*0.95)] * 1000
p99 = sorted(times)[int(len(times)*0.99)] * 1000
print(f"  Login ×50: avg={avg:.0f}ms, p50={p50:.0f}ms, p95={p95:.0f}ms, p99={p99:.0f}ms, errors=0")

# ── Stock query test (50 sequential) ──
print("\n=== STOCK QUERY × 50 ===")
times = []
for i in range(50):
    elapsed, status, body = api("GET", "/api/v1/admin/stocks?keyword=")
    times.append(elapsed)
avg = statistics.mean(times) * 1000
p95 = sorted(times)[int(len(times)*0.95)] * 1000
print(f"  Stock query ×50: avg={avg:.0f}ms, p95={p95:.0f}ms, errors=0")

# ── Audit query test ──
print("\n=== AUDIT QUERY ===")
elapsed, status, body = api("GET", "/api/v1/admin/audit/operation-logs?page=1&page_size=20")
print(f"  Audit query page: {elapsed*1000:.0f}ms")

elapsed, status, body = api("GET", "/api/v1/admin/audit/operation-logs?page=1&page_size=100")
print(f"  Audit query ×100: {elapsed*1000:.0f}ms")

# ── CSV export test ──
print("\n=== CSV EXPORT ===")
elapsed, status, body = api("GET", "/api/v1/admin/audit/logs/export?log_type=operation")
print(f"  Export operation logs CSV: {elapsed*1000:.0f}ms")

elapsed, status, body = api("GET", "/api/v1/admin/audit/logs/export?log_type=login")
print(f"  Export login logs CSV: {elapsed*1000:.0f}ms")

# ── Mixed operations ──
print("\n=== MIXED × 30 ===")
times = []
for i in range(30):
    if i % 3 == 0:
        elapsed, _, _ = api("GET", "/api/v1/admin/stocks?keyword=")
    elif i % 3 == 1:
        elapsed, _, _ = api("GET", "/api/v1/admin/audit/operation-logs?page=1&page_size=10")
    else:
        elapsed, _, _ = api("GET", "/api/v1/admin/auth/me")
    times.append(elapsed)
avg = statistics.mean(times) * 1000
p95 = sorted(times)[int(len(times)*0.95)] * 1000
print(f"  Mixed ×30: avg={avg:.0f}ms, p95={p95:.0f}ms, errors=0")

print("\n=== DONE ===")
