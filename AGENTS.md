# AGENTS.md

## 1. 项目说明

项目名称：`buy-agent`

`buy-agent` 是一个采购中心自动化 Agent。当前消息入口为飞书私聊，后续允许扩展到 Web 前端、钉钉和企业微信。

本仓库负责消息接入、Agent 编排、会话管理、工具调用和后端适配；不负责真实业务数据库和采购后端内部实现。

Codex 在修改代码前必须阅读本文件，并根据任务内容阅读 `docs/` 下对应文档。

---

## 2. 核心约束

### 2.1 只有一个采购 Agent

当前只有：

```text
ProcurementAgent
```

禁止创建：

```text
AgentRouter
GeneralAgent
RequesterAgent
ReviewerAgent
PurchaserAgent
WarehouseAgent
```

四个业务角色不是四个 Agent：

```text
REQUESTER
REVIEWER
PURCHASER
WAREHOUSE
```

角色差异通过 `ToolPolicy` 控制。

### 2.2 当前只支持私聊

当前飞书机器人不处理群聊。

会话键：

```text
procurement:<channel>:<external_tenant_id>:<external_user_id>
```

### 2.3 Agent 不直接访问数据库

禁止在以下目录连接 MySQL 或编写 SQL：

```text
agent/
application/
tools/
adapters/channels/
```

正式业务操作必须通过 `BackendGateway`。

### 2.4 后端接口尚未冻结

当前尚未与后端负责人确定正式 HTTP API。

Codex 不得：

- 猜测正式 URL；
- 将临时请求结构当成最终契约；
- 在 Tool 中直接调用 HTTP；
- 将 HTTP 字段传播到核心领域层；
- 根据 Mock 实现反推真实后端设计。

当前使用：

```text
BackendGateway
MockBackendGateway
```

`HttpBackendGateway` 只允许保留骨架，等待正式接口确认。

### 2.5 卡片回调不经过大模型

以下动作直接进入 `ActionOrchestrator`：

```text
submit_for_review
approve_requirement
reject_requirement
submit_to_purchaser
submit_to_warehouse
complete_warehouse_entry
cancel_requirement
```

禁止再次交给 LLM 理解。

### 2.6 渠道与核心逻辑解耦

以下目录不得导入飞书、钉钉或微信 SDK：

```text
domain/
application/
agent/
ports/
tools/
```

具体渠道实现只能位于：

```text
adapters/channels/
```

核心层不得直接依赖 `open_id`、`chat_id` 或飞书卡片 JSON。

### 2.7 当前不实现 OCR

当前只处理文本。

收到图片时统一回复：

```text
当前暂不支持图片识别，请直接发送采购信息文字。
```

---

## 3. 核心处理链路

### 文本消息

```text
Channel Adapter
→ InboundEvent
→ ChatOrchestrator
→ IdentityService
→ SessionService
→ RequirementResolver
→ ContextBuilder
→ ToolPolicy
→ ProcurementAgent
→ ToolRegistry
→ BackendGateway
→ AgentResponse
→ Channel Renderer/Sender
```

### 卡片动作

```text
Channel Adapter
→ ActionCommand
→ ActionOrchestrator
→ BackendGateway
→ 更新当前卡片
→ 通知下一处理人
```

---

## 4. 代码分层

```text
bootstrap     应用启动、配置和依赖注入
domain        领域模型、枚举和异常
application   用例编排
agent         大模型调用和工具循环
ports         核心层依赖的抽象接口
adapters      飞书、存储、LLM和后端的具体实现
tools         Agent可调用的受控工具
```

依赖方向必须保持：

```text
adapters → ports/application/domain
application → ports/agent/domain/tools
agent/tools → ports/domain
domain → 不依赖外部实现
```

---

## 5. Agent 规则

`ProcurementAgent` 必须：

- 只调用本轮注册的工具；
- 最大执行轮数从配置读取；
- 把工具结果返回模型继续判断；
- 正式保存必须调用工具；
- 一次只追问一个缺失字段；
- 推荐最多展示 3 条；
- 使用会话中的最近推荐解释“第一个”“第二个”；
- 不猜测采购编号；
- 不自行授予角色；
- 不虚构后端执行成功；
- 非采购问题提示当前机器人只支持采购业务。

以下信息必须由程序注入，禁止由模型提供：

```text
user_id
roles
data_scopes
session_key
tenant_id
channel
trace_id
```

---

## 6. Context 与 Memory

Context 每轮动态构建，至少包含：

```text
CurrentPrincipal
SessionContext
RequirementContext
available_tool_names
```

Memory 只保存交互状态：

```text
active_requirement_id
active_role
pending_field
current_stage
summary
recent_messages
last_recommendations
awaiting_action
```

正式业务字段、状态、角色和权限以后端为准。

---

## 7. Tool Policy

本轮可用工具：

```text
角色允许工具
∩
状态允许工具
```

数据权限由后端最终校验。

只向 LLM 注册本轮允许的工具。

---

## 8. 并发、去重与幂等

- 同一 `session_key` 串行；
- 不同 `session_key` 并行；
- 开发版使用 `asyncio.Lock`；
- 通过 `event_id` 和 `message_id` 去重；
- 卡片通过 `action_token` 幂等；
- 不得使用一个全局锁阻塞所有用户。

---

## 9. GitHub 规则

长期分支：

```text
main
develop
```

功能分支：

```text
feature/<issue-number>-<short-name>
fix/<issue-number>-<short-name>
test/<issue-number>-<short-name>
docs/<issue-number>-<short-name>
```

开发流程：

```text
Issue
→ 从 develop 创建分支
→ 开发与测试
→ Commit
→ Push
→ Pull Request 到 develop
→ CI
→ Review
→ 合并
```

Commit 使用 Conventional Commits：

```text
feat: add session store
fix: prevent duplicate card action
test: add concurrency tests
docs: update architecture
```

Codex 不得：

- 直接向 `main` 提交；
- 自动合并 PR；
- 强制推送；
- 删除远程分支；
- 提交 `.env`；
- 修改真实密钥；
- 修改与当前 Issue 无关的文件。

---

## 10. 代码与测试要求

- Python 3.11+；
- 公共接口必须有类型标注；
- 网络 I/O 使用 `async/await`；
- 外部输入使用 Pydantic 校验；
- 核心领域模型优先使用 `dataclass`；
- HTTP 请求必须设置超时；
- 重试必须有限次；
- 不允许静默吞掉异常；
- 不允许使用全局变量保存当前用户或采购单；
- 核心逻辑必须可单元测试。

提交前运行：

```bash
ruff format --check .
ruff check .
mypy src
pytest -q
```

---

## 11. Codex 执行要求

修改前：

1. 阅读本文件；
2. 阅读与任务相关的 `docs/*.md`；
3. 查看当前分支；
4. 查看 `git status`；
5. 阅读相关代码和测试；
6. 明确 Issue 范围；
7. 仅修改必要文件。

完成后输出：

```text
1. 任务理解
2. 修改文件
3. 核心实现
4. 测试命令
5. 测试结果
6. 风险与限制
7. 未完成事项
```

---

## 12. 文档索引

- 架构设计：`docs/architecture.md`
- 职责边界：`docs/backend-boundary.md`
- 后端能力草案：`docs/backend-contract-draft.md`
- 字段与状态：`docs/field-dictionary.md`
- 工具设计：`docs/tool-design.md`
- 独立开发范围：`docs/independent-development.md`
- 测试规范：`docs/testing.md`
- 开发计划：`docs/development-plan.md`
