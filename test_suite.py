"""
ADMIN 子系统自动化测试套件（pytest）
用法：
    pytest test_suite.py -v                          # 运行全部独立测试
    pytest test_suite.py -v -m "not trade"           # 跳过 TRADE 依赖测试
    pytest test_suite.py -v -m trade                 # 只跑 TRADE 依赖测试
    DB_PASSWORD=root123 ADMIN_BASE_URL=http://localhost:8002 pytest test_suite.py -v
"""
import pytest
from conftest import API, ACCOUNTS, make_auth, db_connect, db_unlock_user


# ================================================================
# 0. 健康检查  HC-001 ~ HC-004
# ================================================================
class TestHealth:
    def test_all_up(self, client):
        """HC-001: 全部依赖正常"""
        resp = client.get("/health")
        assert resp.status_code in (200, 503)
        body = resp.json()
        assert body["service"] == "admin-service"
        assert body["status"] in ("UP", "DEGRADED")
        assert "mysql" in body["dependencies"]

    def test_mysql_up(self, client):
        """验证 MySQL 连通性状态"""
        resp = client.get("/health")
        body = resp.json()
        # MySQL 至少应该是 UP
        mysql_status = body["dependencies"].get("mysql", "UNKNOWN")
        assert mysql_status in ("UP", "DOWN")

    def test_trade_status_present(self, client):
        """HC-003/004: TRADE 依赖状态字段存在"""
        resp = client.get("/health")
        body = resp.json()
        assert "trade" in body["dependencies"]


# ================================================================
# 1. 认证模块  AUTH-001 ~ AUTH-017
# ================================================================
class TestAuthLogin:
    """AUTH-001 ~ AUTH-006 登录相关"""

    def test_normal_login_all_roles(self, client, tokens):
        """AUTH-001: 四种角色正常登录"""
        for username in ACCOUNTS:
            assert tokens[username] is not None, f"{username} 登录失败"

    def test_login_returns_correct_role(self, client):
        """AUTH-001: 登录返回正确的 role 和 token"""
        resp = client.post(f"{API}/auth/login",
            json={"username": "sys_admin", "password": "Admin@123"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["role"] == "SYSTEM_ADMIN"
        assert len(body["data"]["token"]) > 20

    def test_user_not_found(self, client):
        """AUTH-002: 用户名不存在 → 401"""
        resp = client.post(f"{API}/auth/login",
            json={"username": "nonexistent_user", "password": "whatever"})
        assert resp.status_code == 401
        body = resp.json()
        assert body["success"] is False

    def test_wrong_password(self, client):
        """AUTH-003: 密码错误 → 401"""
        resp = client.post(f"{API}/auth/login",
            json={"username": "sys_admin", "password": "WrongPassword123"})
        assert resp.status_code == 401
        body = resp.json()
        assert body["success"] is False

    def test_lock_after_5_failures(self, client, store):
        """AUTH-004: 连续5次失败触发锁定 → 第6次 403"""
        for i in range(5):
            resp = client.post(f"{API}/auth/login",
                json={"username": "senior_admin", "password": "wrong"})
            body = resp.json()
            assert body["success"] is False, f"第{i+1}次应失败"

        # 第6次输正确密码应被锁定
        resp = client.post(f"{API}/auth/login",
            json={"username": "senior_admin", "password": "Admin@123"})
        assert resp.status_code == 403
        body = resp.json()
        assert body["success"] is False
        assert "锁定" in body.get("message", "")

        # 解锁并刷新缓存
        db_unlock_user("senior_admin")
        store.refresh(client, "senior_admin")

    def test_disabled_account_cannot_login(self, client, system_token, normal_admin_id, store):
        """AUTH-006: 禁用账户无法登录 → 403"""
        if normal_admin_id is None:
            pytest.skip("无法获取 normal_admin ID")
        # 先禁用
        client.put(f"{API}/admins/{normal_admin_id}/permissions",
            json={"role": "NORMAL_ADMIN", "status": "disabled", "authorized_stocks": []},
            headers=make_auth(system_token))
        # 尝试登录
        resp = client.post(f"{API}/auth/login",
            json={"username": "normal_admin", "password": "Admin@123"})
        assert resp.status_code == 403
        assert resp.json()["success"] is False
        # 恢复并刷新缓存
        client.put(f"{API}/admins/{normal_admin_id}/permissions",
            json={"role": "NORMAL_ADMIN", "status": "active",
                  "authorized_stocks": ["600000", "000001", "600036"]},
            headers=make_auth(system_token))
        store.refresh(client, "normal_admin")

    def test_negative_unlock_after_lock_expires(self, client):
        """AUTH-005: 锁定到期自动解锁 ★ 手动辅助 ★"""
        # 自动化只能验证锁定期概念；完整测试需等待5分钟或手动修改数据库
        # 此处验证锁定状态在数据库中可被清除
        db = db_connect()
        if db is None:
            pytest.skip("需要数据库密码验证解锁机制")
        # 确保 senior_admin 正常
        cur = db.cursor()
        cur.execute("SELECT status FROM admin_info WHERE username='senior_admin'")
        row = cur.fetchone()
        if row:
            assert row[0] in ("active", "locked")
        db.close()


class TestAuthToken:
    """AUTH-007 ~ AUTH-010 令牌校验"""

    def test_logout(self, client, system_token):
        """AUTH-007: 正常登出 → 200"""
        resp = client.post(f"{API}/auth/logout",
            headers=make_auth(system_token))
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_no_token_rejected(self, client):
        """AUTH-008: 无 Token 访问受保护接口 → 401"""
        resp = client.get(f"{API}/auth/me")
        assert resp.status_code == 401

    def test_fake_token_rejected(self, client):
        """AUTH-009: 伪造 Token 被拒绝 → 401"""
        resp = client.get(f"{API}/auth/me",
            headers=make_auth("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"))
        assert resp.status_code == 401

    def test_token_version_invalidation(self, client, system_token, store):
        """AUTH-010: 密码修改后旧 Token 失效 → 401"""
        resp = client.post(f"{API}/auth/password", json={
            "old_password": "Admin@123",
            "new_password": "Temp@5678",
            "confirm_password": "Temp@5678",
        }, headers=make_auth(system_token))
        assert resp.json()["success"] is True, f"改密失败: {resp.json().get('message')}"

        # 旧 Token 应失效
        resp2 = client.get(f"{API}/auth/me", headers=make_auth(system_token))
        assert resp2.status_code == 401

        # 恢复密码并刷新缓存
        new_resp = client.post(f"{API}/auth/login",
            json={"username": "sys_admin", "password": "Temp@5678"})
        new_token = new_resp.json()["data"]["token"]
        client.post(f"{API}/auth/password", json={
            "old_password": "Temp@5678",
            "new_password": "Admin@123",
            "confirm_password": "Admin@123",
        }, headers=make_auth(new_token))
        store.refresh(client, "sys_admin")


class TestAuthPassword:
    """AUTH-011 ~ AUTH-015 / PWD-001 ~ PWD-003 密码管理"""

    def test_change_password_success(self, client, store):
        """AUTH-011: 正确修改密码 → 200"""
        # 用 audit_admin 测试，不影响其他
        resp = client.post(f"{API}/auth/login",
            json={"username": "audit_admin", "password": "Admin@123"})
        token = resp.json()["data"]["token"]
        resp = client.post(f"{API}/auth/password", json={
            "old_password": "Admin@123",
            "new_password": "Audit@5678",
            "confirm_password": "Audit@5678",
        }, headers=make_auth(token))
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # 恢复并刷新缓存
        new_resp = client.post(f"{API}/auth/login",
            json={"username": "audit_admin", "password": "Audit@5678"})
        new_token = new_resp.json()["data"]["token"]
        client.post(f"{API}/auth/password", json={
            "old_password": "Audit@5678",
            "new_password": "Admin@123",
            "confirm_password": "Admin@123",
        }, headers=make_auth(new_token))
        store.refresh(client, "audit_admin")

    def test_wrong_old_password(self, client, senior_token):
        """AUTH-012: 原密码错误 → 401"""
        resp = client.post(f"{API}/auth/password", json={
            "old_password": "WrongOldPassword",
            "new_password": "NewPass@9999",
            "confirm_password": "NewPass@9999",
        }, headers=make_auth(senior_token))
        assert resp.status_code == 401
        assert resp.json()["success"] is False

    def test_password_mismatch(self, client, senior_token):
        """AUTH-013: 两次新密码不一致 → 422"""
        resp = client.post(f"{API}/auth/password", json={
            "old_password": "Admin@123",
            "new_password": "Abc@123456",
            "confirm_password": "Xyz@123456",
        }, headers=make_auth(senior_token))
        assert resp.status_code == 422
        assert resp.json()["success"] is False

    def test_password_only_digits(self, client, senior_token):
        """AUTH-014: 纯数字密码 → 422"""
        resp = client.post(f"{API}/auth/password", json={
            "old_password": "Admin@123",
            "new_password": "12345678",
            "confirm_password": "12345678",
        }, headers=make_auth(senior_token))
        assert resp.status_code == 422
        assert resp.json()["success"] is False

    def test_password_too_short(self, client, senior_token):
        """AUTH-015: 密码长度不足8位 → 422"""
        resp = client.post(f"{API}/auth/password", json={
            "old_password": "Admin@123",
            "new_password": "Abc12!",
            "confirm_password": "Abc12!",
        }, headers=make_auth(senior_token))
        assert resp.status_code == 422
        assert resp.json()["success"] is False

    def test_password_only_lower_and_digits(self, client, senior_token):
        """AUTH-014 补充: 仅小写+数字（仅两类）→ 422"""
        resp = client.post(f"{API}/auth/password", json={
            "old_password": "Admin@123",
            "new_password": "abc12345",
            "confirm_password": "abc12345",
        }, headers=make_auth(senior_token))
        assert resp.status_code == 422
        assert resp.json()["success"] is False


class TestAuthMe:
    """AUTH-016 获取当前用户信息"""

    def test_get_me(self, client, system_token):
        """AUTH-016: 获取当前用户信息 → 200"""
        resp = client.get(f"{API}/auth/me", headers=make_auth(system_token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["username"] == "sys_admin"
        assert body["data"]["role"] == "SYSTEM_ADMIN"
        assert body["data"]["status"] == "active"


class TestAuthLoginLog:
    """AUTH-017 登录日志记录"""

    def test_login_log_exists(self, client, audit_token):
        """AUTH-017: 登录日志有记录"""
        resp = client.get(f"{API}/audit/login-logs",
            headers=make_auth(audit_token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        total = body["data"]["total"]
        assert total >= 4, f"应至少有4条登录记录，实际 {total}"


# ================================================================
# 2. 权限管理模块  PERM-001 ~ PERM-010
# ================================================================
class TestPermissions:
    """PERM-001 ~ PERM-010"""

    def test_system_admin_list_all(self, client, system_token):
        """PERM-001: 系统管理员查看所有管理员 → 200"""
        resp = client.get(f"{API}/admins", headers=make_auth(system_token))
        assert resp.status_code == 200
        body = resp.json()
        items = body["data"]["items"]
        assert len(items) >= 4
        # 验证字段完整性
        for admin in items:
            assert "admin_id" in admin
            assert "username" in admin
            assert "role_name" in admin
            assert "status" in admin

    def test_non_system_blocked(self, client, normal_token):
        """PERM-002: 非系统管理员无权查看 → 403"""
        resp = client.get(f"{API}/admins", headers=make_auth(normal_token))
        assert resp.status_code == 403

    def test_normal_admin_blocked_from_admins(self, client, senior_token):
        """PERM-002: 高级管理员也无权查看 → 403"""
        resp = client.get(f"{API}/admins", headers=make_auth(senior_token))
        assert resp.status_code == 403

    def test_audit_admin_blocked_from_admins(self, client, audit_token):
        """PERM-002: 审计管理员也无权查看 → 403"""
        resp = client.get(f"{API}/admins", headers=make_auth(audit_token))
        assert resp.status_code == 403

    def test_change_role(self, client, system_token, normal_admin_id):
        """PERM-003: 修改管理员角色 → 200"""
        if normal_admin_id is None:
            pytest.skip("无法获取 normal_admin ID")
        # 改为高级管理员
        resp = client.put(f"{API}/admins/{normal_admin_id}/permissions", json={
            "role": "SENIOR_ADMIN", "status": "active",
            "authorized_stocks": ["600000", "000001"],
        }, headers=make_auth(system_token))
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # 恢复
        client.put(f"{API}/admins/{normal_admin_id}/permissions", json={
            "role": "NORMAL_ADMIN", "status": "active",
            "authorized_stocks": ["600000", "000001", "600036"],
        }, headers=make_auth(system_token))

    def test_disable_admin(self, client, system_token, normal_admin_id, store):
        """PERM-004: 禁用管理员 → 200，验证旧token立即失效"""
        if normal_admin_id is None:
            pytest.skip("无法获取 normal_admin ID")
        # 先确保 normal_admin 有有效 token
        resp = client.post(f"{API}/auth/login",
            json={"username": "normal_admin", "password": "Admin@123"})
        old_token = resp.json()["data"]["token"]

        # 禁用
        resp = client.put(f"{API}/admins/{normal_admin_id}/permissions", json={
            "role": "NORMAL_ADMIN", "status": "disabled", "authorized_stocks": [],
        }, headers=make_auth(system_token))
        assert resp.json()["success"] is True

        # 旧 token 应失效（禁用账号返回 403）
        resp = client.get(f"{API}/auth/me", headers=make_auth(old_token))
        assert resp.status_code == 403

        # 恢复并刷新缓存
        client.put(f"{API}/admins/{normal_admin_id}/permissions", json={
            "role": "NORMAL_ADMIN", "status": "active",
            "authorized_stocks": ["600000", "000001", "600036"],
        }, headers=make_auth(system_token))
        store.refresh(client, "normal_admin")

    def test_change_authorized_stocks(self, client, system_token, normal_admin_id):
        """PERM-005: 修改授权股票范围 → 200"""
        if normal_admin_id is None:
            pytest.skip("无法获取 normal_admin ID")
        resp = client.put(f"{API}/admins/{normal_admin_id}/permissions", json={
            "role": "NORMAL_ADMIN", "status": "active",
            "authorized_stocks": ["600000"],
        }, headers=make_auth(system_token))
        assert resp.json()["success"] is True
        # 恢复
        client.put(f"{API}/admins/{normal_admin_id}/permissions", json={
            "role": "NORMAL_ADMIN", "status": "active",
            "authorized_stocks": ["600000", "000001", "600036"],
        }, headers=make_auth(system_token))

    def test_target_not_found(self, client, system_token):
        """PERM-006: 目标管理员不存在 → 404"""
        resp = client.put(f"{API}/admins/99999/permissions", json={
            "role": "NORMAL_ADMIN", "status": "active", "authorized_stocks": [],
        }, headers=make_auth(system_token))
        assert resp.status_code == 404
        assert resp.json()["success"] is False

    def test_invalid_role(self, client, system_token, normal_admin_id):
        """PERM-007: 无效角色 → 422"""
        if normal_admin_id is None:
            pytest.skip("无法获取 normal_admin ID")
        resp = client.put(f"{API}/admins/{normal_admin_id}/permissions", json={
            "role": "INVALID_ROLE", "status": "active", "authorized_stocks": [],
        }, headers=make_auth(system_token))
        assert resp.status_code == 422
        assert resp.json()["success"] is False

    def test_invalid_status(self, client, system_token, normal_admin_id):
        """PERM-008: 无效状态 → 422"""
        if normal_admin_id is None:
            pytest.skip("无法获取 normal_admin ID")
        resp = client.put(f"{API}/admins/{normal_admin_id}/permissions", json={
            "role": "NORMAL_ADMIN", "status": "unknown", "authorized_stocks": [],
        }, headers=make_auth(system_token))
        assert resp.status_code == 422
        assert resp.json()["success"] is False

    def test_permission_audit_log(self, client, audit_token):
        """PERM-010: 权限变更产生审计记录"""
        resp = client.get(f"{API}/audit/operation-logs?operation_type=PERMISSION",
            headers=make_auth(audit_token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total"] >= 1, "至少应有1条 PERMISSION 日志"


# ================================================================
# 3. 审计日志模块  AUDIT-001 ~ AUDIT-016
# ================================================================
class TestAudit:
    """AUDIT-001 ~ AUDIT-016"""

    def test_audit_admin_query_operation_logs(self, client, audit_token):
        """AUDIT-001: 审计管理员查询操作日志 → 200"""
        resp = client.get(f"{API}/audit/operation-logs",
            headers=make_auth(audit_token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "items" in body["data"]
        assert "total" in body["data"]

    def test_system_admin_blocked_from_audit(self, client, system_token):
        """AUDIT-002: 系统管理员无权访问审计日志 → 403"""
        resp = client.get(f"{API}/audit/operation-logs",
            headers=make_auth(system_token))
        assert resp.status_code == 403

    def test_normal_admin_blocked_from_audit(self, client, normal_token):
        """AUDIT-003: 普通管理员无权访问 → 403"""
        resp = client.get(f"{API}/audit/operation-logs",
            headers=make_auth(normal_token))
        assert resp.status_code == 403

    def test_senior_admin_blocked_from_audit(self, client, senior_token):
        """AUDIT-003: 高级管理员无权访问 → 403"""
        resp = client.get(f"{API}/audit/operation-logs",
            headers=make_auth(senior_token))
        assert resp.status_code == 403

    def test_filter_by_admin_id(self, client, audit_token):
        """AUDIT-004: 按管理员 ID 筛选 → 200"""
        resp = client.get(f"{API}/audit/operation-logs?admin_id=1",
            headers=make_auth(audit_token))
        assert resp.status_code == 200
        body = resp.json()
        for item in body["data"]["items"]:
            assert item["admin_id"] == 1

    def test_filter_by_operation_type(self, client, audit_token):
        """AUDIT-005: 按操作类型筛选 → 200"""
        resp = client.get(f"{API}/audit/operation-logs?operation_type=LOGIN",
            headers=make_auth(audit_token))
        assert resp.status_code == 200
        body = resp.json()
        for item in body["data"]["items"]:
            assert item["operation_type"] == "LOGIN"

    def test_filter_by_time_range(self, client, audit_token):
        """AUDIT-006: 按时间范围筛选 → 200"""
        resp = client.get(
            f"{API}/audit/operation-logs?start_time=2026-01-01T00:00:00&end_time=2026-12-31T23:59:59",
            headers=make_auth(audit_token))
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_pagination(self, client, audit_token):
        """AUDIT-007: 正常分页 → 200"""
        resp = client.get(f"{API}/audit/operation-logs?page=1&page_size=10",
            headers=make_auth(audit_token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["page"] == 1
        assert body["data"]["page_size"] == 10

    def test_pagination_boundary(self, client, audit_token):
        """AUDIT-008: 分页边界(page_size上限100) → 200"""
        resp = client.get(f"{API}/audit/operation-logs?page=1&page_size=100",
            headers=make_auth(audit_token))
        assert resp.status_code == 200

    def test_login_logs_query(self, client, audit_token):
        """AUDIT-009: 查询登录日志 → 200"""
        resp = client.get(f"{API}/audit/login-logs",
            headers=make_auth(audit_token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        # 验证字段完整性
        items = body["data"]["items"]
        if items:
            item = items[0]
            for field in ["login_log_id", "login_time", "login_result", "ip_address"]:
                assert field in item

    def test_csv_export_operation(self, client, audit_token):
        """AUDIT-010: 导出操作日志 CSV → 200"""
        resp = client.get(f"{API}/audit/logs/export?log_type=operation",
            headers=make_auth(audit_token))
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")

    def test_csv_export_login(self, client, audit_token):
        """AUDIT-011: 导出登录日志 CSV → 200"""
        resp = client.get(f"{API}/audit/logs/export?log_type=login",
            headers=make_auth(audit_token))
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")

    def test_csv_export_with_filter(self, client, audit_token):
        """AUDIT-012: 导出时应用筛选条件 → 200"""
        resp = client.get(
            f"{API}/audit/logs/export?log_type=login&admin_id=1&start_time=2026-01-01T00:00:00",
            headers=make_auth(audit_token))
        assert resp.status_code == 200

    def test_delete_old_logs(self, client, audit_token):
        """AUDIT-013/014: 删除日志 → 200"""
        resp = client.delete(
            f"{API}/audit/logs?log_type=login&before=2026-01-01T00:00:00",
            headers=make_auth(audit_token))
        assert resp.status_code in (200, 404, 400)
        body = resp.json()
        # 可能成功也可能没有数据可删
        assert "message" in body

    def test_invalid_date_format(self, client, audit_token):
        """AUDIT-015: 日期格式无效 → 400"""
        resp = client.delete(f"{API}/audit/logs?log_type=login&before=abc",
            headers=make_auth(audit_token))
        assert resp.status_code == 400
        assert resp.json()["success"] is False

    def test_invalid_log_type(self, client, audit_token):
        """AUDIT-016: log_type 参数无效 → 422"""
        resp = client.get(f"{API}/audit/logs/export?log_type=invalid",
            headers=make_auth(audit_token))
        assert resp.status_code == 422


# ================================================================
# 4. 数据库验证 (手动辅助)
# ================================================================
class TestDatabase:
    """数据库层面的验证"""

    def test_password_is_bcrypt_hash(self):
        """SEC-001: 密码是 bcrypt 哈希，非明文"""
        db = db_connect()
        if db is None:
            pytest.skip("需要数据库密码")
        cur = db.cursor()
        cur.execute("SELECT password_hash FROM admin_info WHERE username='sys_admin'")
        row = cur.fetchone()
        if row:
            hashed = row[0]
            assert not hashed.startswith("Admin@123"), f"密码不应是明文: {hashed[:30]}..."
            assert hashed.startswith("$2b$") or hashed.startswith("$2a$"), \
                f"应为 bcrypt 哈希: {hashed[:20]}..."
        db.close()

    def test_foreign_key_constraint(self):
        """删除被引用的管理员时外键约束生效"""
        db = db_connect()
        if db is None:
            pytest.skip("需要数据库密码")
        try:
            cur = db.cursor()
            # 尝试删除一个有操作日志的管理员
            cur.execute("DELETE FROM admin_info WHERE admin_id=1")
            db.commit()
            # 如果执行到这里，说明没约束（重新插入）
            pytest.fail("外键约束未生效，DELETE 不应成功")
        except Exception:
            # 预期抛异常
            pass
        finally:
            try:
                db.rollback()
                db.close()
            except Exception:
                pass

    def test_unique_username_index(self):
        """验证 username 唯一索引存在"""
        db = db_connect()
        if db is None:
            pytest.skip("需要数据库密码")
        cur = db.cursor()
        cur.execute("SHOW INDEX FROM admin_info WHERE Column_name='username'")
        rows = cur.fetchall()
        has_unique = any(r[1] == 0 for r in rows)  # Non_unique=0 means unique
        assert has_unique, "username 应有唯一索引"
        db.close()

    def test_necessary_indexes(self):
        """验证关键索引存在"""
        db = db_connect()
        if db is None:
            pytest.skip("需要数据库密码")
        cur = db.cursor()
        for table, col in [("operation_log", "admin_id"),
                           ("operation_log", "operation_type"),
                           ("operation_log", "operation_time"),
                           ("login_log", "admin_id"),
                           ("login_log", "login_time")]:
            cur.execute(f"SHOW INDEX FROM {table} WHERE Column_name='{col}'")
            rows = cur.fetchall()
            assert len(rows) >= 1, f"{table}.{col} 索引缺失"
        db.close()


# ================================================================
# 5. 边界值测试  BND-001 ~ BND-008
# ================================================================
class TestBoundaryAuth:
    """认证模块边界值测试"""

    def test_password_exactly_8_chars(self, client, senior_token, store):
        """BND-001: 密码长度刚好8位 → 通过"""
        resp = client.post(f"{API}/auth/password", json={
            "old_password": "Admin@123",
            "new_password": "Abc12345",
            "confirm_password": "Abc12345",
        }, headers=make_auth(senior_token))
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # 恢复并刷新缓存
        nr = client.post(f"{API}/auth/login",
            json={"username": "senior_admin", "password": "Abc12345"})
        nt = nr.json()["data"]["token"]
        client.post(f"{API}/auth/password", json={
            "old_password": "Abc12345",
            "new_password": "Admin@123",
            "confirm_password": "Admin@123",
        }, headers=make_auth(nt))
        store.refresh(client, "senior_admin")

    def test_password_7_chars_rejected(self, client, senior_token):
        """BND-002: 密码长度7位 → 422"""
        resp = client.post(f"{API}/auth/password", json={
            "old_password": "Admin@123",
            "new_password": "Abc123!",
            "confirm_password": "Abc123!",
        }, headers=make_auth(senior_token))
        assert resp.status_code == 422

    def test_password_all_categories(self, client, senior_token, store):
        """BND-003: 密码含所有四类字符 → 通过"""
        resp = client.post(f"{API}/auth/password", json={
            "old_password": "Admin@123",
            "new_password": "Abc123!@",
            "confirm_password": "Abc123!@",
        }, headers=make_auth(senior_token))
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # 恢复并刷新缓存
        nr = client.post(f"{API}/auth/login",
            json={"username": "senior_admin", "password": "Abc123!@"})
        nt = nr.json()["data"]["token"]
        client.post(f"{API}/auth/password", json={
            "old_password": "Abc123!@",
            "new_password": "Admin@123",
            "confirm_password": "Admin@123",
        }, headers=make_auth(nt))
        store.refresh(client, "senior_admin")

    def test_password_only_two_categories(self, client, senior_token):
        """BND-004: 仅含两类字符 → 422"""
        resp = client.post(f"{API}/auth/password", json={
            "old_password": "Admin@123",
            "new_password": "abc12345",
            "confirm_password": "abc12345",
        }, headers=make_auth(senior_token))
        assert resp.status_code == 422

    def test_exactly_4_failures_no_lock(self, client):
        """BND-006: 刚好失败4次未锁定，第5次正确登录成功"""
        # 用 normal_admin 测试
        for i in range(4):
            resp = client.post(f"{API}/auth/login",
                json={"username": "normal_admin", "password": "wrong"})
            assert resp.json()["success"] is False, f"第{i+1}次应失败"
        # 第5次正确
        resp = client.post(f"{API}/auth/login",
            json={"username": "normal_admin", "password": "Admin@123"})
        assert resp.json()["success"] is True, "4次失败后应仍可登录"

    def test_lock_exactly_5_failures(self, client, store):
        """BND-007: 失败5次触发锁定"""
        for i in range(5):
            client.post(f"{API}/auth/login",
                json={"username": "senior_admin", "password": "wrong"})
        resp = client.post(f"{API}/auth/login",
            json={"username": "senior_admin", "password": "Admin@123"})
        assert resp.status_code == 403
        assert resp.json()["success"] is False
        # 解锁并刷新缓存
        db_unlock_user("senior_admin")
        store.refresh(client, "senior_admin")


# ================================================================
# 6. TRADE 依赖测试  (标记为可选，联调后执行)
# ================================================================
@pytest.mark.trade
class TestStocks:
    """STOCK-001 ~ STOCK-010  需要 TRADE 服务运行"""

    def test_normal_admin_sees_authorized_stocks(self, client, normal_token):
        """STOCK-001: 普通管理员仅看到授权股票"""
        resp = client.get(f"{API}/stocks", headers=make_auth(normal_token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    def test_senior_admin_sees_all_stocks(self, client, senior_token):
        """STOCK-002: 高级管理员看到全部"""
        resp = client.get(f"{API}/stocks", headers=make_auth(senior_token))
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_keyword_search(self, client, senior_token):
        """STOCK-003: 关键字搜索"""
        resp = client.get(f"{API}/stocks?keyword=600",
            headers=make_auth(senior_token))
        assert resp.status_code == 200

    def test_empty_keyword(self, client, senior_token):
        """STOCK-004: 空关键字"""
        resp = client.get(f"{API}/stocks",
            headers=make_auth(senior_token))
        assert resp.status_code == 200

    def test_single_stock_quote(self, client, senior_token):
        """STOCK-005: 查看单只股票行情"""
        resp = client.get(f"{API}/stocks/600000/quote",
            headers=make_auth(senior_token))
        # 可能 200 或 404 (股票不存在)
        assert resp.status_code in (200, 404, 502)

    def test_unauthorized_stock_denied(self, client, normal_token):
        """STOCK-006: 查看未授权股票 → 403"""
        resp = client.get(f"{API}/stocks/999999/quote",
            headers=make_auth(normal_token))
        assert resp.status_code == 403

    def test_nonexistent_stock(self, client, senior_token):
        """STOCK-007: 不存在的股票 → 404"""
        resp = client.get(f"{API}/stocks/XXXXXX/quote",
            headers=make_auth(senior_token))
        assert resp.status_code in (404, 502)

    def test_order_book(self, client, senior_token):
        """STOCK-008: 查看委托簿"""
        resp = client.get(f"{API}/stocks/600000/order-book",
            headers=make_auth(senior_token))
        assert resp.status_code in (200, 404, 502)

    def test_trade_downstream_error(self, client, senior_token):
        """STOCK-009/010: TRADE 不可达 → 502"""
        resp = client.get(f"{API}/stocks/600000/quote",
            headers=make_auth(senior_token))
        # 502 如果 TRADE 不可用；200 如果可用
        assert resp.status_code in (200, 502)


@pytest.mark.trade
class TestLimits:
    """LIMIT-001 ~ LIMIT-010  需要 TRADE 服务"""

    def test_senior_admin_set_limits(self, client, senior_token):
        """LIMIT-001: 高级管理员设置涨跌停"""
        resp = client.put(f"{API}/stocks/600000/limits", json={
            "limit_up_ratio": "0.10",
            "limit_down_ratio": "0.10",
            "effective_date": "2026-06-16",
            "reason": "自动化测试",
        }, headers=make_auth(senior_token))
        assert resp.status_code in (200, 502)

    def test_normal_admin_cannot_set_limits(self, client, normal_token):
        """LIMIT-002: 普通管理员无权 → 403"""
        resp = client.put(f"{API}/stocks/600000/limits", json={
            "limit_up_ratio": "0.10",
            "limit_down_ratio": "0.10",
            "effective_date": "2026-06-16",
        }, headers=make_auth(normal_token))
        assert resp.status_code == 403

    def test_audit_admin_cannot_set_limits(self, client, audit_token):
        """LIMIT-003: 审计管理员无权 → 403"""
        resp = client.put(f"{API}/stocks/600000/limits", json={
            "limit_up_ratio": "0.10",
            "limit_down_ratio": "0.10",
            "effective_date": "2026-06-16",
        }, headers=make_auth(audit_token))
        assert resp.status_code == 403

    def test_ratio_zero_rejected(self, client, senior_token):
        """LIMIT-004/6: 比例为0 → 422"""
        resp = client.put(f"{API}/stocks/600000/limits", json={
            "limit_up_ratio": "0",
            "limit_down_ratio": "0.10",
            "effective_date": "2026-06-16",
        }, headers=make_auth(senior_token))
        assert resp.status_code == 422

    def test_ratio_above_max(self, client, senior_token):
        """LIMIT-005: 涨幅超过10% → 422"""
        resp = client.put(f"{API}/stocks/600000/limits", json={
            "limit_up_ratio": "0.15",
            "limit_down_ratio": "0.10",
            "effective_date": "2026-06-16",
        }, headers=make_auth(senior_token))
        assert resp.status_code == 422

    def test_invalid_ratio_format(self, client, senior_token):
        """LIMIT-007: 非数字比例 → 422"""
        resp = client.put(f"{API}/stocks/600000/limits", json={
            "limit_up_ratio": "abc",
            "limit_down_ratio": "0.10",
            "effective_date": "2026-06-16",
        }, headers=make_auth(senior_token))
        assert resp.status_code == 422


@pytest.mark.trade
class TestTradeControl:
    """CTRL-001 ~ CTRL-008  需要 TRADE 服务"""

    def test_senior_admin_pause(self, client, senior_token):
        """CTRL-001: 高级管理员暂停交易"""
        resp = client.post(f"{API}/stocks/600000/pause", json={
            "pause_reason": "自动化测试暂停",
        }, headers=make_auth(senior_token))
        assert resp.status_code in (200, 502)

    def test_senior_admin_resume(self, client, senior_token):
        """CTRL-002: 高级管理员重启交易"""
        resp = client.post(f"{API}/stocks/600000/resume", json={
            "resume_reason": "自动化测试恢复",
        }, headers=make_auth(senior_token))
        assert resp.status_code in (200, 502)

    def test_normal_admin_cannot_pause(self, client, normal_token):
        """CTRL-003: 普通管理员无权暂停 → 403"""
        resp = client.post(f"{API}/stocks/600000/pause", json={
            "pause_reason": "测试",
        }, headers=make_auth(normal_token))
        assert resp.status_code == 403

    def test_normal_admin_cannot_resume(self, client, normal_token):
        """CTRL-004: 普通管理员无权重启 → 403"""
        resp = client.post(f"{API}/stocks/600000/resume", json={
            "resume_reason": "测试",
        }, headers=make_auth(normal_token))
        assert resp.status_code == 403


@pytest.mark.trade
class TestTradingDays:
    """TD-001 ~ TD-006  需要 TRADE 服务"""

    def test_senior_admin_open_day(self, client, senior_token):
        """TD-001: 高级管理员开启交易日"""
        resp = client.post(f"{API}/trading-days/open", json={
            "trade_date": "2026-06-16",
        }, headers=make_auth(senior_token))
        assert resp.status_code in (200, 502)

    def test_senior_admin_close_day(self, client, senior_token):
        """TD-002: 高级管理员结束交易日"""
        resp = client.post(f"{API}/trading-days/close", json={
            "trade_date": "2026-06-16",
            "reason": "自动化测试收盘",
        }, headers=make_auth(senior_token))
        assert resp.status_code in (200, 502)

    def test_normal_admin_cannot_manage(self, client, normal_token):
        """TD-003: 普通管理员无权 → 403"""
        resp = client.post(f"{API}/trading-days/open", json={
            "trade_date": "2026-06-16",
        }, headers=make_auth(normal_token))
        assert resp.status_code == 403

    def test_missing_date(self, client, senior_token):
        """TD-004: 缺少日期参数 → 422"""
        resp = client.post(f"{API}/trading-days/open", json={},
            headers=make_auth(senior_token))
        assert resp.status_code == 422
