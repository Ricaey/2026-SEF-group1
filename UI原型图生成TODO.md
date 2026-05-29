# UI 原型图生成 TODO

本文档列出系统设计报告第 5 章所需的所有 UI 原型图，包括内容说明和可直接使用的 AI 生成提示词。

风格约定：管理后台风格，蓝色主色调，Element Plus 组件风格，左侧导航 + 顶部导航栏布局，表格 + 表单控件为主。

---

## 1. ui_login.png — 登录界面

**内容**：
- 居中蓝色渐变背景
- 居中白色登录卡片（圆角阴影），标题"股票交易管理系统"
- 用户名输入框（带用户图标前缀）
- 密码输入框（带锁图标前缀）
- "登录"按钮（蓝色，通栏宽度）
- 底部小字"验证码登录功能将在后续版本开放"

**提示词**：
> A clean admin login page UI mockup. Centered login card on a blue gradient background. Card title "股票交易管理系统" in Chinese. Username input field with user icon, password input field with lock icon. A full-width blue "登录" button. Minimal, professional, Element Plus design style. No real data, wireframe/mockup style.

---

## 2. ui_stock_view.png — 股票查看主界面

**内容**：
- 顶部导航栏：左侧系统名"股票交易管理系统"，右侧用户名"管理员001" + 退出按钮
- 左侧侧边栏菜单：股票查看（高亮）、涨跌停设置、交易控制、密码修改
- 主区域上方：搜索框（支持代码/名称/板块）+ 搜索按钮
- 主区域中部：股票列表表格（列：代码、名称、类型、最新价、涨跌幅、成交量、状态），数据行用占位符（如 600000、浦发银行、NORMAL、10.05、+2.3%、1,234,567、OPEN），状态列用绿色圆点
- 主区域底部：分页器

**提示词**：
> A stock market admin panel dashboard UI mockup. Top navigation bar with system name "股票交易管理系统" and user info. Left sidebar menu with items: 股票查看 (highlighted), 涨跌停设置, 交易控制, 密码修改. Main area has a search bar, a data table showing stock list with columns: 代码, 名称, 类型, 最新价, 涨跌幅, 成交量, 状态. Clean blue-themed admin UI, Element Plus style, wireframe quality. No real data, placeholder text only.

---

## 3. ui_limit_set.png — 涨跌停设置界面

**内容**：
- 顶部导航栏、左侧菜单栏同上，涨跌停设置高亮
- 主区域上方：股票选择区（多选下拉框 + 搜索）
- 主区域中部表单区：
  - 涨幅比例输入框（placeholder: "0.10"）+ 标签"如 0.10 表示 +10%"
  - 跌幅比例输入框（placeholder: "0.10"）+ 标签"如 0.10 表示 -10%"
  - 生效日期选择器（默认显示次日日期，灰色不可编辑）
- 主区域下方预览区（虚线框）：
  - 昨日收盘价：10.00
  - 计算涨停价：11.00
  - 计算跌停价：9.00
  - 小字说明"以上价格由中央交易系统计算并返回"
- 底部"提交"（蓝色）和"重置"按钮

**提示词**：
> A stock limit setting form UI mockup. Admin panel with left sidebar (涨跌停设置 highlighted). Main area shows a form: a multi-select stock picker, two input fields for limit up/down ratio (placeholder "0.10"), a date picker defaulting to next day. Below the form is a dashed-border preview box showing: 昨日收盘价: 10.00, 涨停价: 11.00, 跌停价: 9.00. A blue "提交" button and a "重置" button at the bottom. Blue-themed Element Plus admin style, mockup quality, Chinese labels.

---

## 4. ui_trade_control.png — 交易控制界面（含交易日管理）

**内容**：
- 顶部导航栏、左侧菜单栏同上，交易控制高亮
- 主区域顶部两个 Tab：交易暂停/重启 | 交易日管理
- Tab1 内容：
  - 股票下拉选择器 + 当前状态标签（OPEN 绿色 / PAUSED 红色 / CLOSED 灰色）
  - "暂停交易"按钮（红色），点击后弹出模态框"请输入暂停原因" + 文本区 + 确认/取消
  - "重启交易"按钮（绿色），已暂停时可用
- Tab2 内容：
  - 交易日状态卡片：当前状态"已开始"（绿色）/ "已结束"（灰色）
  - "开始交易日"按钮（蓝色，未开始时可用）
  - "结束交易日"按钮（橙色，已开始时可用，点击弹出二次确认框）

**提示词**:
> A trade control admin panel UI mockup with two tabs. First tab "交易暂停/重启" shows a stock selector, status indicator (OPEN in green/PAUSED in red), a red "暂停交易" button and a green "重启交易" button. Second tab "交易日管理" shows a trading day status card (已开始 in green or 已结束 in gray), a blue "开始交易日" button and an orange "结束交易日" button. Blue-themed Element Plus admin style, Chinese labels, mockup/wireframe quality.

---

## 5. ui_permission.png — 权限管理界面

**内容**：
- 顶部导航栏、左侧菜单栏，权限管理高亮
- 主区域：管理员列表表格
  - 列：用户名、角色（下拉可编辑）、状态（标签：active 绿 / locked 红 / disabled 灰）、授权股票数、最近登录时间、操作
  - 操作列含"编辑"按钮
- 点击"编辑"弹出侧边面板或模态框：
  - 角色下拉框（普通管理员 / 高级管理员 / 审计管理员）
  - 授权股票多选选择器（600000 浦发银行 ☑, 000001 平安银行 ☑）
  - 账号状态下拉框（active / locked / disabled）
  - "保存"和"取消"按钮
- 底部小字"仅可管理非自身的其他管理员"

**提示词**:
> A permission management admin panel UI mockup. Left sidebar with 权限管理 highlighted. Main area shows a table of admin accounts with columns: 用户名, 角色, 状态 (green active/red locked/gray disabled tags), 授权股票数, 最近登录, 操作. An edit side panel is visible: role dropdown (普通管理员/高级管理员/审计管理员), authorized stocks multi-select, status dropdown, "保存" and "取消" buttons. Blue-themed Element Plus style, Chinese, wireframe quality.

---

## 6. ui_audit.png — 审计日志界面

**内容**：
- 顶部导航栏、左侧菜单栏，审计日志高亮
- 主区域顶部筛选区：
  - 操作管理员下拉选择
  - 操作类型下拉选择（登录/查询/涨跌停设置/交易控制/交易日管理/密码修改/权限变更/账号状态变更）
  - 时间范围日期选择器（起始 → 结束）
  - "查询"按钮 + "导出 CSV"按钮
- 主区域中部两个 Tab：操作日志 | 登录日志
- Tab 内容：日志列表表格
  - 操作日志 Tab：列（时间、操作管理员、操作类型、目标对象、详情、结果、IP）
  - 登录日志 Tab：列（登录时间、登出时间、管理员、结果、失败原因、IP）
- 底部分页器

**提示词**:
> An audit log admin panel UI mockup. Left sidebar with 审计日志 highlighted. Top filter area: admin dropdown, operation type dropdown, date range picker, "查询" and "导出 CSV" buttons. Two tabs below: 操作日志 and 登录日志. Below tabs is a data table showing audit log entries with columns: 时间, 操作管理员, 操作类型, 目标对象, 详情, 结果, IP. Clean blue-themed Element Plus admin style, Chinese, mockup quality.

---

## 7. ui_password.png — 密码修改界面

**内容**：
- 居中布局（非左侧菜单导航，而是独立的设置页）
- 顶部标题"修改登录密码"
- 表单区居中卡片（宽度约 400px）：
  - 原密码输入框
  - 新密码输入框 + 下方密码强度指示条（弱=红色/中=黄色/强=绿色三段条）
  - 确认密码输入框
- 密码要求小字说明："长度 ≥ 8，须含大写字母、小写字母、数字、特殊字符中至少三类"
- "确认修改"按钮（蓝色）+ "取消"按钮

**提示词**:
> A password change form UI mockup. Centered card layout, title "修改登录密码". Three input fields: 原密码, 新密码 (with a password strength indicator bar below: weak red/medium yellow/strong green), 确认密码. Below fields a note "长度 ≥ 8，须含大写字母、小写字母、数字、特殊字符中至少三类". Blue "确认修改" button and a "取消" button. Minimal, centered dialog style, blue-themed Element Plus design, Chinese, mockup quality.

---

## 生成建议

- 推荐工具：Figma / 即时设计 / draw.io / V0.dev（AI 生成前端原型）
- 分辨率：1440×900 或 1920×1080
- 导出格式：PNG，命名对应文档引用
- 所有图确保中文渲染正确（部分 AI 工具中文支持弱，可能需要后处理）
- 可先用 draw.io 手工绘制低保真线框图，再用 Figma 美化
