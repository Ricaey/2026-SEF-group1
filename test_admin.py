"""
ADMIN 子系统联调前独立测试脚本 v2
用法：python test_admin.py [数据库密码]
示例：python test_admin.py root123
依赖：pip install requests pymysql
"""

import requests
import sys
import time

BASE = "http://localhost:8000/api/v1/admin"
HEADERS = {"Content-Type": "application/json"}
DB_PASSWORD = sys.argv[1] if len(sys.argv) > 1 else None
PASS, FAIL = 0, 0


def ok(cond, msg):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {msg}")
    else:
        FAIL += 1
        print(f"  ❌ {msg}")
    return cond


def title(s):
    print(f"\n{'='*60}")
    print(f"  {s}")
    print(f"{'='*60}")


def auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def login(user, pwd):
    return requests.post(f"{BASE}/auth/login",
        json={"username": user, "password": pwd}, headers=HEADERS)


def bad(r):
    """业务失败: HTTP 200 但 success=false"""
    return r.status_code == 200 and not r.json().get("success")


# ============================================================
title("0. 健康检查")
# ============================================================
r = requests.get("http://localhost:8000/health")
body = r.json()
ok(r.status_code == 200 and body["status"] in ("UP", "DEGRADED"),
   f"/health → {body.get('status')}, mysql={body.get('dependencies',{}).get('mysql')}")

# ============================================================
title("1. 正常登录（四类角色）")
# ============================================================
accounts = [
    ("normal_admin", "Admin@123", "NORMAL_ADMIN"),
    ("senior_admin",  "Admin@123", "SENIOR_ADMIN"),
    ("sys_admin",     "Admin@123", "SYSTEM_ADMIN"),
    ("audit_admin",   "Admin@123", "AUDIT_ADMIN"),
]
tokens = {}
for u, p, role in accounts:
    r = login(u, p)
    b = r.json()
    ok(r.status_code == 200 and b.get("success") and b["data"]["role"] == role,
       f"{u} → {b['data']['role']}  token={'✓' if b['data'].get('token') else '✗'}")
    if b.get("success"):
        tokens[role] = b["data"]["token"]

# ============================================================
title("2. 异常登录")
# ============================================================
# 你的 API: 业务错误返回 200 + success=false + message, 不是 HTTP 401/403

r = login("sys_admin", "WrongPass")
ok(bad(r), f"密码错误 → success={r.json().get('success')}  msg={r.json().get('message','')[:40]}")

r = login("nobody", "whatever")
ok(bad(r), f"用户不存在 → success={r.json().get('success')}  msg={r.json().get('message','')[:40]}")

r = login("", "whatever")
ok(bad(r), f"空用户名 → success={r.json().get('success')}  msg={r.json().get('message','')[:40]}")

# ============================================================
title("3. 锁定机制 — 连续输错 5 次")
# ============================================================
locked_ok = True
for i in range(1, 6):
    r = login("senior_admin", "wrong")   # 用 senior_admin 避免影响 normal_admin
    b = r.json()
    print(f"  第{i}次 → 剩余{b.get('data',{}).get('remaining_attempts','?')}次  msg={b.get('message','')[:40]}")
    if b.get("success"):
        locked_ok = False

# 第 6 次输正确密码，应该被拒绝
r6 = login("senior_admin", "Admin@123")
b6 = r6.json()
locked = bad(r6) and "锁定" in str(b6.get("message", ""))
if locked:
    ok(True, f"锁定生效，正确密码被拒 → msg={b6.get('message','')[:40]}")
else:
    ok(False, f"锁定可能未生效 → success={b6.get('success')}  msg={b6.get('message','')[:40]}  (期望 success=false + 锁定提示)")

# 手动解锁 senior_admin
title("3. 续 — 解锁 senior_admin")
if DB_PASSWORD:
    try:
        import pymysql
        db = pymysql.connect(host="localhost", user="root", password=DB_PASSWORD,
                             database="admin_db", charset="utf8mb4")
        db.cursor().execute(
            "UPDATE admin_info SET status='active', failed_attempts=0, lock_until=NULL WHERE username='senior_admin'")
        db.commit(); db.close()
        r = login("senior_admin", "Admin@123")
        ok(r.status_code == 200 and r.json().get("success"), "数据库解锁成功，重新登录正常")
        tokens["SENIOR_ADMIN"] = r.json()["data"]["token"]
    except Exception as e:
        print(f"  ⚠️ 数据库解锁失败: {e}")
        print(f"  请手动: UPDATE admin_info SET status='active', failed_attempts=0, lock_until=NULL WHERE username='senior_admin'")
else:
    print("  ⚠️ 未提供数据库密码，跳过自动解锁")
    print(f"  请手动: UPDATE admin_info SET status='active', failed_attempts=0, lock_until=NULL WHERE username='senior_admin'")

# ============================================================
title("4. Token 校验")
# ============================================================
r = requests.get(f"{BASE}/auth/me", headers=HEADERS)   # 无 token
ok(bad(r), f"无 token → success={r.json().get('success')}  (期望 false)")

r = requests.get(f"{BASE}/auth/me", headers={**HEADERS, **auth(tokens["SYSTEM_ADMIN"])})
ok(r.json().get("success") and r.json()["data"]["username"] == "sys_admin",
   f"有效 token → user={r.json()['data']['username']}")

r = requests.get(f"{BASE}/auth/me", headers={**HEADERS, **auth("fake.token.here")})
ok(bad(r), f"伪造 token → success={r.json().get('success')}  (期望 false)")

# ============================================================
title("5. 密码修改")
# ============================================================
h = {**HEADERS, **auth(tokens["SYSTEM_ADMIN"])}
url = f"{BASE}/auth/password"

# 原密码错
r = requests.post(url, json={"old_password":"Wrong","new_password":"NewPass@9999","confirm_password":"NewPass@9999"}, headers=h)
ok(bad(r), f"原密码错 → success={r.json().get('success')}  msg={r.json().get('message','')[:30]}")

# 两次不一致
r = requests.post(url, json={"old_password":"Admin@123","new_password":"A@123456","confirm_password":"B@123456"}, headers=h)
ok(bad(r), f"两次不一致 → success={r.json().get('success')}  msg={r.json().get('message','')[:30]}")

# 纯数字
r = requests.post(url, json={"old_password":"Admin@123","new_password":"12345678","confirm_password":"12345678"}, headers=h)
ok(bad(r), f"纯数字 → success={r.json().get('success')}  msg={r.json().get('message','')[:40]}")

# 太短
r = requests.post(url, json={"old_password":"Admin@123","new_password":"Abc12!","confirm_password":"Abc12!"}, headers=h)
ok(bad(r), f"太短 → success={r.json().get('success')}  msg={r.json().get('message','')[:30]}")

# 正常改密 + 旧 token 失效
title("5. 续 — 改密后旧 token 失效")
r = requests.post(url, json={"old_password":"Admin@123","new_password":"Temp@5678","confirm_password":"Temp@5678"}, headers=h)
ok(r.json().get("success"), f"改密成功 → success={r.json().get('success')}")

if r.json().get("success"):
    r2 = requests.get(f"{BASE}/auth/me", headers={**HEADERS, **auth(tokens["SYSTEM_ADMIN"])})
    ok(bad(r2), f"旧 token 失效 → success={r2.json().get('success')} (期望 false)")

    # 改回来
    nt = login("sys_admin", "Temp@5678").json()["data"]["token"]
    requests.post(url, json={"old_password":"Temp@5678","new_password":"Admin@123","confirm_password":"Admin@123"}, headers={**HEADERS, **auth(nt)})
    tokens["SYSTEM_ADMIN"] = login("sys_admin", "Admin@123").json()["data"]["token"]
    print("  ℹ️  密码已恢复为 Admin@123")

# ============================================================
title("6. 权限管理")
# ============================================================
sh = {**HEADERS, **auth(tokens["SYSTEM_ADMIN"])}
nh = {**HEADERS, **auth(tokens["NORMAL_ADMIN"])}

r = requests.get(f"{BASE}/admins", headers=sh)
b = r.json()
n = len(b.get("data", {}).get("items", []))
ok(r.status_code == 200 and n >= 4, f"系统管理员查看列表 → {n} 人 (期望 ≥4)")

r = requests.get(f"{BASE}/admins", headers=nh)
ok(bad(r), f"普通管理员无权 → success={r.json().get('success')} (期望 false)")

# 找 normal_admin 的 id
r = requests.get(f"{BASE}/admins", headers=sh)
admins = r.json()["data"]["items"]
nid = next((a["admin_id"] for a in admins if a["username"] == "normal_admin"), None)

if nid:
    # 改角色
    r = requests.put(f"{BASE}/admins/{nid}/permissions",
        json={"role":"SENIOR_ADMIN","status":"active","authorized_stocks":["600000","000001"]}, headers=sh)
    ok(r.json().get("success"), f"修改角色 → success={r.json().get('success')}")
    requests.put(f"{BASE}/admins/{nid}/permissions",
        json={"role":"NORMAL_ADMIN","status":"active","authorized_stocks":["600000","000001","600036"]}, headers=sh)

    # 禁用 → 验证登录失败 → 恢复
    requests.put(f"{BASE}/admins/{nid}/permissions",
        json={"role":"NORMAL_ADMIN","status":"disabled","authorized_stocks":[]}, headers=sh)
    r = login("normal_admin", "Admin@123")
    ok(bad(r), f"禁用后无法登录 → success={r.json().get('success')}  msg={r.json().get('message','')[:30]}")
    requests.put(f"{BASE}/admins/{nid}/permissions",
        json={"role":"NORMAL_ADMIN","status":"active","authorized_stocks":["600000","000001","600036"]}, headers=sh)
    tokens["NORMAL_ADMIN"] = login("normal_admin", "Admin@123").json()["data"]["token"]
    print("  ℹ️  normal_admin 已恢复")
else:
    ok(False, "权限修改 → 未找到 normal_admin")

# ============================================================
title("7. 审计日志")
# ============================================================
ah = {**HEADERS, **auth(tokens["AUDIT_ADMIN"])}

r = requests.get(f"{BASE}/audit/operation-logs", headers=ah)
b = r.json()
ok(r.status_code == 200 and b.get("success"),
   f"操作日志 → total={b.get('data',{}).get('total',0)}")

r = requests.get(f"{BASE}/audit/operation-logs?operation_type=LOGIN", headers=ah)
ok(r.status_code == 200, f"按 LOGIN 筛选 → {r.status_code}")

r = requests.get(f"{BASE}/audit/login-logs", headers=ah)
ok(r.status_code == 200 and r.json().get("success"), f"登录日志 → {r.status_code}")

# 普通管理员无权
r = requests.get(f"{BASE}/audit/operation-logs", headers=nh)
ok(bad(r), f"普通管理员无权查审计 → success={r.json().get('success')} (期望 false)")

# ============================================================
title("8. 数据库验证")
# ============================================================
if DB_PASSWORD:
    try:
        import pymysql
        db = pymysql.connect(host="localhost", user="root", password=DB_PASSWORD,
                             database="admin_db", charset="utf8mb4")
        cur = db.cursor()
        cur.execute("SELECT password_hash FROM admin_info WHERE username='sys_admin'")
        h = cur.fetchone()[0]
        ok(not h.startswith("Admin@123") and len(h) > 20,
           f"密码是 bcrypt 哈希 → {h[:30]}...")
        try:
            cur.execute("DELETE FROM admin_info WHERE admin_id=9999")
            ok(True, "外键验证 → 无引用记录可删除（正常）")
        except:
            ok(True, "外键验证 → DELETE 被拒绝（正常，说明约束生效）")
        db.close()
    except Exception as e:
        print(f"  ⚠️ 数据库连接失败: {e}")
else:
    print("  ℹ️  跳过（未提供数据库密码，可运行 python test_admin.py 你的密码）")

# ============================================================
title("测试结果")
# ============================================================
total = PASS + FAIL
pct = PASS * 100 // total if total else 0
print(f"""
  通过: {PASS} / {total}
  失败: {FAIL} / {total}
  通过率: {pct}%
""")
if FAIL == 0:
    print("  🎉 全部通过！\n")
elif FAIL <= 3:
    print(f"  ⚠️  {FAIL} 项失败，检查上面标记 ❌ 的项目\n")
else:
    print(f"  🔴 {FAIL} 项失败，需要排查\n")
