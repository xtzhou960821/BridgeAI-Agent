# BridgeAI-Site REST API 设计 v1.0

> **产品名称：** BridgeAI-Site 智慧工地 AI Agent 平台  
> **文档类型：** REST API 设计  
> **适用阶段：** 第一阶段 MVP  
> **编制单位：** 浙江悟联信息科技有限公司  
> **编制人：** 周仙通  
> **版本：** v1.0  
> **后端技术基线：** FastAPI + Pydantic + SQLAlchemy + Alembic  
> **协议基线：** HTTPS + REST + JSON + WebSocket  
> **认证方式：** JWT Access Token + Refresh Token  
> **接口版本：** `/api/v1`

---

# 1. 文档目的

本文件用于统一 BridgeAI-Site 第一阶段 MVP 的 REST API 设计，包括：

- URL 命名；
- 认证与授权；
- 请求与响应结构；
- 分页、筛选和排序；
- 错误码；
- 幂等性；
- 文件上传；
- WebSocket 实时事件；
- Agent 工具调用接口；
- OpenAPI 文档；
- 版本管理；
- 接口验收。

本文件是前后端联调、Agent 工具开发、第三方集成和自动化测试的直接依据。

---

# 2. API 设计目标

API 必须满足：

1. 资源边界清晰；
2. 命名一致；
3. 权限可控；
4. 写操作可审计；
5. 可重复调用；
6. 支持分页、筛选、排序；
7. 支持视频、AI、告警和工单闭环；
8. 支持 Agent 受控调用；
9. 支持未来多项目、多租户扩展；
10. 支持 OpenAPI 自动生成。

---

# 3. 基础约定

## 3.1 Base URL

```text
https://{host}/api/v1
```

开发环境：

```text
http://localhost:8000/api/v1
```

---

## 3.2 Content-Type

普通 JSON：

```http
Content-Type: application/json
```

文件上传：

```http
Content-Type: multipart/form-data
```

---

## 3.3 字符编码

统一 UTF-8。

---

## 3.4 时间格式

统一使用 ISO 8601：

```text
2026-07-23T09:30:00+09:00
```

数据库使用 `timestamptz`。

---

## 3.5 ID 格式

统一使用 UUID 字符串：

```text
550e8400-e29b-41d4-a716-446655440000
```

---

# 4. URL 命名规范

## 4.1 资源使用复数名词

正确：

```text
/projects
/cameras
/events
/work-orders
```

避免：

```text
/getProjects
/createCamera
```

---

## 4.2 使用 HTTP 方法表达动作

| 方法 | 语义 |
|---|---|
| GET | 查询 |
| POST | 创建 |
| PUT | 全量更新 |
| PATCH | 局部更新 |
| DELETE | 删除或软删除 |

---

## 4.3 业务动作接口

无法自然映射 CRUD 的动作使用：

```text
POST /events/{id}/confirm
POST /events/{id}/ignore
POST /work-orders/{id}/submit
POST /work-orders/{id}/approve
POST /work-orders/{id}/reject
```

---

# 5. 认证与授权

## 5.1 登录

```http
POST /auth/login
```

请求：

```json
{
  "username": "admin",
  "password": "********",
  "captcha_id": "optional",
  "captcha_code": "optional"
}
```

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "access_token": "jwt",
    "refresh_token": "jwt",
    "token_type": "Bearer",
    "expires_in": 1800,
    "user": {
      "id": "uuid",
      "display_name": "管理员"
    }
  },
  "request_id": "req_xxx"
}
```

---

## 5.2 Token 刷新

```http
POST /auth/refresh
```

---

## 5.3 当前用户

```http
GET /auth/me
```

---

## 5.4 退出登录

```http
POST /auth/logout
```

---

## 5.5 Authorization Header

```http
Authorization: Bearer {access_token}
```

---

## 5.6 权限控制

权限粒度：

```text
resource:action
```

示例：

```text
project:read
camera:create
event:confirm
work_order:approve
agent:execute
```

接口层同时校验：

- 登录状态；
- 企业权限；
- 项目权限；
- 角色权限；
- 资源归属；
- 数据状态。

---

# 6. 统一响应结构

## 6.1 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "request_id": "req_xxx"
}
```

---

## 6.2 分页响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "page": 1,
    "page_size": 20,
    "total": 100,
    "pages": 5
  },
  "request_id": "req_xxx"
}
```

---

## 6.3 错误响应

```json
{
  "code": 400101,
  "message": "参数校验失败",
  "details": [
    {
      "field": "name",
      "reason": "不能为空"
    }
  ],
  "request_id": "req_xxx"
}
```

---

# 7. 错误码规范

## 7.1 HTTP 状态码

| 状态码 | 说明 |
|---|---|
| 200 | 成功 |
| 201 | 创建成功 |
| 202 | 已接受异步任务 |
| 204 | 无响应体 |
| 400 | 参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 409 | 状态冲突 |
| 422 | 数据校验失败 |
| 429 | 请求过多 |
| 500 | 服务异常 |
| 503 | 服务不可用 |

---

## 7.2 业务错误码

建议六位：

```text
模块编号 + 错误编号
```

示例：

| 错误码 | 说明 |
|---|---|
| 401001 | Token 无效 |
| 403001 | 无项目权限 |
| 404101 | 项目不存在 |
| 409201 | 摄像头编码重复 |
| 409301 | 事件状态不允许确认 |
| 409401 | 工单状态不允许提交 |
| 503501 | AI 推理服务不可用 |

---

# 8. 分页、筛选与排序

## 8.1 分页参数

```text
page=1
page_size=20
```

最大 `page_size` 建议 200。

---

## 8.2 排序

```text
sort_by=occurred_at
sort_order=desc
```

---

## 8.3 时间范围

```text
date_from=2026-07-01T00:00:00+09:00
date_to=2026-07-23T23:59:59+09:00
```

---

## 8.4 多值筛选

```text
status=pending,confirmed
risk_level=level_1,level_2
```

---

## 8.5 搜索

```text
keyword=安全帽
```

---

# 9. 幂等性

对创建工单、生成报表、Agent 写操作等重要接口支持：

```http
Idempotency-Key: {uuid}
```

服务端保存一定时间内的幂等结果。

---

# 10. 项目接口

## 10.1 项目列表

```http
GET /projects
```

参数：

- keyword；
- status；
- organization_id；
- page；
- page_size。

---

## 10.2 创建项目

```http
POST /projects
```

---

## 10.3 项目详情

```http
GET /projects/{project_id}
```

---

## 10.4 更新项目

```http
PATCH /projects/{project_id}
```

---

## 10.5 删除项目

```http
DELETE /projects/{project_id}
```

默认软删除。

---

## 10.6 项目概览

```http
GET /projects/{project_id}/overview
```

返回：

- 今日告警；
- 高风险数；
- 待整改数；
- 逾期数；
- 摄像头在线率；
- AI 任务运行率。

---

# 11. 标段与区域接口

```http
GET    /projects/{project_id}/sections
POST   /projects/{project_id}/sections
GET    /sections/{section_id}
PATCH  /sections/{section_id}
DELETE /sections/{section_id}
```

区域：

```http
GET    /projects/{project_id}/zones
POST   /projects/{project_id}/zones
GET    /zones/{zone_id}
PATCH  /zones/{zone_id}
DELETE /zones/{zone_id}
```

空间查询：

```http
GET /projects/{project_id}/zones/within
```

参数：

- bbox；
- zone_type；
- risk_level。

---

# 12. 用户、角色与权限接口

## 12.1 用户

```http
GET    /users
POST   /users
GET    /users/{user_id}
PATCH  /users/{user_id}
DELETE /users/{user_id}
```

---

## 12.2 角色

```http
GET    /roles
POST   /roles
GET    /roles/{role_id}
PATCH  /roles/{role_id}
DELETE /roles/{role_id}
```

---

## 12.3 权限

```http
GET /permissions
GET /roles/{role_id}/permissions
PUT /roles/{role_id}/permissions
```

---

## 12.4 项目角色

```http
GET  /projects/{project_id}/members
POST /projects/{project_id}/members
DELETE /projects/{project_id}/members/{user_id}
```

---

# 13. 摄像头接口

## 13.1 摄像头列表

```http
GET /cameras
```

筛选：

- project_id；
- section_id；
- zone_id；
- status；
- ai_status；
- vendor；
- keyword。

---

## 13.2 创建摄像头

```http
POST /cameras
```

请求示例：

```json
{
  "project_id": "uuid",
  "zone_id": "uuid",
  "name": "1号门摄像头",
  "code": "CAM-001",
  "vendor": "ezviz",
  "source_type": "ezviz",
  "source_config": {
    "device_serial": "xxx",
    "channel_no": 1
  },
  "location": {
    "type": "Point",
    "coordinates": [121.1234567, 28.1234567]
  }
}
```

---

## 13.3 摄像头详情

```http
GET /cameras/{camera_id}
```

---

## 13.4 更新摄像头

```http
PATCH /cameras/{camera_id}
```

---

## 13.5 删除摄像头

```http
DELETE /cameras/{camera_id}
```

---

## 13.6 测试视频源

```http
POST /cameras/{camera_id}/test-stream
```

---

## 13.7 获取播放地址

```http
POST /cameras/{camera_id}/playback-token
```

返回短期播放地址。

---

## 13.8 摄像头状态

```http
GET /cameras/{camera_id}/status
GET /cameras/{camera_id}/status-history
```

---

# 14. 视频与媒体接口

## 14.1 手动抓图

```http
POST /cameras/{camera_id}/snapshot
```

---

## 14.2 开始录像

```http
POST /cameras/{camera_id}/recordings/start
```

---

## 14.3 停止录像

```http
POST /cameras/{camera_id}/recordings/stop
```

---

## 14.4 录像列表

```http
GET /recordings
```

---

## 14.5 媒体文件

```http
GET    /media-files/{media_file_id}
DELETE /media-files/{media_file_id}
POST   /media-files/{media_file_id}/download-token
```

---

## 14.6 上传文件

```http
POST /media-files/upload
```

使用 `multipart/form-data`。

---

# 15. AI 模型接口

## 15.1 模型列表

```http
GET /ai/models
```

---

## 15.2 注册模型

```http
POST /ai/models
```

---

## 15.3 上传模型文件

```http
POST /ai/models/{model_id}/files
```

---

## 15.4 发布模型

```http
POST /ai/models/{model_id}/publish
```

---

## 15.5 回滚模型

```http
POST /ai/models/{model_id}/rollback
```

---

## 15.6 模型指标

```http
GET /ai/models/{model_id}/metrics
```

---

# 16. AI 节点接口

```http
GET    /ai/nodes
POST   /ai/nodes
GET    /ai/nodes/{node_id}
PATCH  /ai/nodes/{node_id}
DELETE /ai/nodes/{node_id}
POST   /ai/nodes/{node_id}/test
GET    /ai/nodes/{node_id}/metrics
```

---

# 17. AI 任务接口

## 17.1 任务列表

```http
GET /ai/tasks
```

---

## 17.2 创建任务

```http
POST /ai/tasks
```

请求示例：

```json
{
  "project_id": "uuid",
  "camera_id": "uuid",
  "model_id": "uuid",
  "ai_node_id": "uuid",
  "name": "1号门安全帽识别",
  "frame_interval_ms": 200,
  "cooldown_seconds": 30,
  "inference_config": {
    "confidence_threshold": 0.5,
    "imgsz": 640
  },
  "rule_config": {
    "event_type": "no_helmet",
    "min_duration_seconds": 2
  },
  "roi_config": {
    "zones": []
  }
}
```

---

## 17.3 启用任务

```http
POST /ai/tasks/{task_id}/enable
```

---

## 17.4 停用任务

```http
POST /ai/tasks/{task_id}/disable
```

---

## 17.5 测试任务

```http
POST /ai/tasks/{task_id}/test
```

---

## 17.6 任务指标

```http
GET /ai/tasks/{task_id}/metrics
```

---

# 18. 告警事件接口

## 18.1 事件列表

```http
GET /events
```

筛选：

- project_id；
- section_id；
- zone_id；
- camera_id；
- event_type；
- risk_level；
- status；
- date_from；
- date_to；
- keyword。

---

## 18.2 事件详情

```http
GET /events/{event_id}
```

---

## 18.3 确认事件

```http
POST /events/{event_id}/confirm
```

请求：

```json
{
  "risk_level": "level_2",
  "comment": "确认违规"
}
```

---

## 18.4 忽略事件

```http
POST /events/{event_id}/ignore
```

---

## 18.5 标记误报

```http
POST /events/{event_id}/false-positive
```

---

## 18.6 修改风险等级

```http
POST /events/{event_id}/risk-level
```

---

## 18.7 创建工单

```http
POST /events/{event_id}/work-order
```

---

## 18.8 批量处理

```http
POST /events/batch/confirm
POST /events/batch/ignore
POST /events/batch/export
```

---

## 18.9 事件统计

```http
GET /events/statistics
```

返回：

- 趋势；
- 类型分布；
- 风险等级分布；
- 区域排名；
- 班组排名；
- 摄像头排名。

---

# 19. 整改工单接口

## 19.1 工单列表

```http
GET /work-orders
```

---

## 19.2 创建工单

```http
POST /work-orders
```

---

## 19.3 工单详情

```http
GET /work-orders/{work_order_id}
```

---

## 19.4 更新工单

```http
PATCH /work-orders/{work_order_id}
```

---

## 19.5 发布工单

```http
POST /work-orders/{work_order_id}/issue
```

---

## 19.6 接单

```http
POST /work-orders/{work_order_id}/accept
```

---

## 19.7 提交整改

```http
POST /work-orders/{work_order_id}/submit
```

---

## 19.8 上传整改证据

```http
POST /work-orders/{work_order_id}/evidence
```

---

## 19.9 复核通过

```http
POST /work-orders/{work_order_id}/approve
```

---

## 19.10 复核驳回

```http
POST /work-orders/{work_order_id}/reject
```

---

## 19.11 关闭工单

```http
POST /work-orders/{work_order_id}/close
```

---

## 19.12 工单时间线

```http
GET /work-orders/{work_order_id}/timeline
```

---

## 19.13 工单统计

```http
GET /work-orders/statistics
```

---

# 20. 驾驶舱接口

```http
GET /dashboard/overview
GET /dashboard/risk-trend
GET /dashboard/event-distribution
GET /dashboard/camera-status
GET /dashboard/work-order-status
GET /dashboard/zone-ranking
GET /dashboard/team-ranking
GET /dashboard/latest-events
```

所有接口需支持：

- project_id；
- date_from；
- date_to。

---

# 21. GIS 接口

## 21.1 GIS 总览

```http
GET /gis/projects/{project_id}/overview
```

---

## 21.2 摄像头 GeoJSON

```http
GET /gis/projects/{project_id}/cameras
```

---

## 21.3 告警 GeoJSON

```http
GET /gis/projects/{project_id}/events
```

---

## 21.4 区域 GeoJSON

```http
GET /gis/projects/{project_id}/zones
```

---

## 21.5 空间范围查询

```http
POST /gis/query
```

请求：

```json
{
  "project_id": "uuid",
  "geometry": {
    "type": "Polygon",
    "coordinates": []
  },
  "layers": ["cameras", "events", "zones"]
}
```

---

# 22. 报表接口

## 22.1 报表列表

```http
GET /reports
```

---

## 22.2 创建报表任务

```http
POST /reports
```

返回 `202 Accepted`。

---

## 22.3 报表任务状态

```http
GET /reports/{report_id}/status
```

---

## 22.4 下载报表

```http
POST /reports/{report_id}/download-token
```

---

## 22.5 重新生成

```http
POST /reports/{report_id}/regenerate
```

---

# 23. Agent 接口

## 23.1 创建会话

```http
POST /agent/sessions
```

---

## 23.2 会话列表

```http
GET /agent/sessions
```

---

## 23.3 会话消息

```http
GET /agent/sessions/{session_id}/messages
```

---

## 23.4 发送消息

```http
POST /agent/sessions/{session_id}/messages
```

请求：

```json
{
  "content": "查询今天所有高风险事件，并给出处置建议",
  "stream": true
}
```

---

## 23.5 运行详情

```http
GET /agent/runs/{run_id}
```

---

## 23.6 工具调用确认

```http
POST /agent/tool-calls/{tool_call_id}/confirm
```

---

## 23.7 工具调用拒绝

```http
POST /agent/tool-calls/{tool_call_id}/reject
```

---

## 23.8 快捷指令

```http
GET /agent/quick-commands
```

---

# 24. Agent 工具接口

Agent 内部工具应走受控 API。

## 24.1 查询事件

```http
POST /agent/tools/query-events
```

---

## 24.2 查询工单

```http
POST /agent/tools/query-work-orders
```

---

## 24.3 查询摄像头状态

```http
POST /agent/tools/query-camera-status
```

---

## 24.4 查询区域风险

```http
POST /agent/tools/query-zone-risk
```

---

## 24.5 生成日报草稿

```http
POST /agent/tools/generate-daily-report
```

---

## 24.6 创建工单草稿

```http
POST /agent/tools/create-work-order-draft
```

必须返回 `requires_confirmation=true`。

---

# 25. 审计接口

```http
GET /audit/logs
GET /audit/logs/{audit_id}
GET /audit/login-logs
GET /audit/agent-runs
```

仅管理员和审计角色可访问。

---

# 26. 文件上传设计

## 26.1 普通上传

```http
POST /media-files/upload
```

限制：

- 文件类型；
- 文件大小；
- MIME；
- 病毒扫描预留；
- checksum；
- 项目归属。

---

## 26.2 大文件分片上传

后续可支持：

```http
POST /uploads/init
POST /uploads/{upload_id}/parts
POST /uploads/{upload_id}/complete
```

---

# 27. WebSocket 设计

## 27.1 连接地址

```text
wss://{host}/ws/v1
```

---

## 27.2 认证

连接时携带 Token。

---

## 27.3 订阅主题

```json
{
  "action": "subscribe",
  "topics": [
    "project.{project_id}.events",
    "project.{project_id}.cameras",
    "project.{project_id}.work-orders"
  ]
}
```

---

## 27.4 实时事件格式

```json
{
  "type": "event.created",
  "topic": "project.xxx.events",
  "data": {},
  "timestamp": "2026-07-23T09:30:00+09:00"
}
```

---

## 27.5 Agent 流式输出

```json
{
  "type": "agent.delta",
  "run_id": "uuid",
  "content": "正在查询..."
}
```

---

# 28. OpenAPI 管理

FastAPI 自动生成：

```text
/docs
/redoc
/openapi.json
```

生产环境建议：

- `/docs` 仅内网；
- OpenAPI 文件纳入版本管理；
- 前端根据 OpenAPI 生成 TypeScript SDK；
- 接口变更必须更新版本说明。

---

# 29. API 版本管理

## 29.1 URL 版本

```text
/api/v1
/api/v2
```

---

## 29.2 兼容原则

- 新增字段保持兼容；
- 删除字段先标记 deprecated；
- 重大变更升级版本；
- 响应字段不随意改名；
- 枚举扩展需前端兼容未知值。

---

# 30. 限流设计

建议：

- 登录：5 次/分钟；
- 普通查询：120 次/分钟；
- 文件上传：20 次/分钟；
- Agent 对话：30 次/分钟；
- 报表生成：10 次/小时；
- 视频 Token：60 次/分钟。

---

# 31. 缓存策略

适合缓存：

- 权限；
- 字典；
- 项目配置；
- 驾驶舱短周期统计；
- 摄像头状态；
- GIS 图层；
- Agent 快捷指令。

缓存必须有明确失效策略。

---

# 32. 审计要求

以下接口必须写审计日志：

- 登录；
- 用户和角色变更；
- 项目变更；
- 摄像头配置变更；
- AI 任务启停；
- 事件确认、忽略；
- 工单发布、提交、复核；
- 报表导出；
- Agent 写操作；
- 文件删除。

---

# 33. API 安全要求

- 全部使用 HTTPS；
- 防止越权；
- 防止 SQL 注入；
- 防止路径遍历；
- 文件类型白名单；
- 请求大小限制；
- Token 过期；
- Refresh Token 轮换；
- CORS 白名单；
- 日志脱敏；
- 播放 Token 短期有效。

---

# 34. 接口测试要求

## 34.1 单元测试

覆盖：

- 参数校验；
- 权限；
- 状态机；
- 错误码；
- 幂等性。

---

## 34.2 集成测试

覆盖：

- 项目；
- 摄像头；
- AI 任务；
- 告警；
- 工单；
- 报表；
- Agent。

---

## 34.3 性能测试

目标：

- 列表接口 P95 < 800ms；
- 详情接口 P95 < 500ms；
- 驾驶舱接口 P95 < 1.5s；
- WebSocket 告警延迟 < 1s；
- 10 万事件分页稳定；
- 20 并发用户稳定。

---

# 35. API 验收标准

## 35.1 通用验收

- OpenAPI 可访问；
- 请求响应统一；
- 错误码统一；
- 权限正确；
- 分页正确；
- 审计完整；
- 幂等有效；
- 时间格式统一；
- UUID 格式统一。

---

## 35.2 业务闭环验收

必须完成：

```text
创建项目
→ 创建摄像头
→ 创建 AI 任务
→ 生成告警事件
→ 确认事件
→ 创建工单
→ 提交整改
→ 复核通过
→ 关闭工单
→ 生成报表
→ Agent 查询全过程
```

---

# 36. 推荐代码结构

```text
app/
├── api/
│   └── v1/
│       ├── auth.py
│       ├── projects.py
│       ├── cameras.py
│       ├── ai.py
│       ├── events.py
│       ├── work_orders.py
│       ├── reports.py
│       └── agent.py
├── models/
├── schemas/
├── services/
├── repositories/
├── permissions/
├── tasks/
├── integrations/
├── agents/
├── core/
└── tests/
```

---

# 37. 与后续文档关系

```text
REST API 设计
    ↓
前端 TypeScript SDK
    ↓
Agent 工具接口
    ↓
接口自动化测试
    ↓
部署与网关配置
```

---

# 38. 总结

BridgeAI-Site 第一阶段 API 采用 REST + WebSocket 的组合方式：

1. REST 负责业务资源和状态变更；
2. WebSocket 负责实时告警、设备状态和 Agent 流式输出；
3. 视频通过 WebRTC/HLS 独立承载；
4. Agent 通过受控工具接口访问业务；
5. 所有写操作经过权限、状态机、幂等和审计；
6. OpenAPI 作为前后端和第三方集成的统一契约。

本设计完成后，BridgeAI-Site 已具备进入前后端联调、Agent 工具开发和接口自动化测试阶段的基础。
