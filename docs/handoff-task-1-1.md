# buy-agent 工作交接：Task 1.1 前置编排边界处理

更新时间：2026-07-28
仓库：`yayi4529/buy-agent`

## 1. 接手前必须阅读

开始操作前阅读：

- `AGENTS.md`
- `docs/architecture.md`
- `docs/backend-boundary.md`
- `docs/independent-development.md`
- `docs/testing.md`

必须继续遵守：

- 只有一个 `ProcurementAgent`，不得创建 `AgentRouter` 或角色 Agent。
- 不接真实 HTTP 后端、数据库、飞书 SDK、LLM、OCR 或群聊。
- Agent 不直接访问数据库，正式业务能力只能通过 `BackendGateway`。
- 当前后端 HTTP 契约尚未冻结，不得猜测 URL 或正式请求结构。

## 2. 已完成并合并的工作

GitHub Issue：

- `#3 Implement pre-agent orchestration pipeline`
- https://github.com/yayi4529/buy-agent/issues/3

已合并 PR：

- `#4 feat: implement pre-agent orchestration pipeline`
- https://github.com/yayi4529/buy-agent/pull/4
- 合并提交：`9c9296e`

PR #4 已实现：

```text
InboundEvent
→ ChatOrchestrator
→ IdentityService
→ SessionService
→ RequirementResolver
→ ContextBuilder
→ ToolPolicy
→ FakeProcurementAgent
→ FakeChannel
```

基础能力包括：

- 领域模型和 Protocol Ports。
- Fake Backend、Fake Agent、Fake Channel。
- Memory Session、Message、Event Store。
- 每个 `session_key` 独立的 `asyncio.Lock`。
- 采购单确定性解析和角色/状态工具过滤。
- 重复 `event_id`、同 session 串行、不同 session 并行测试。

## 3. 当前分支和工作区状态

当前分支：

```text
feature/1-1-pre-agent-boundaries
```

该分支从已包含 PR #4 的最新 `develop` 创建：

```text
9c9296e Merge pull request #4
```

Task 1.1 的改动目前：

- 已写入工作区。
- 尚未 commit。
- 尚未 push。
- 尚未创建新的 GitHub Issue 或 PR。

不要丢弃或覆盖当前未提交改动。

## 4. Task 1.1 已实现内容

### 4.1 event_id 与 message_id 独立去重

`EventStore` 已调整为：

```python
async def is_duplicate(
    *,
    event_id: str,
    message_id: str | None,
) -> bool:
    ...

async def mark_completed(
    *,
    event_id: str,
    message_id: str | None,
) -> None:
    ...
```

语义：

- `event_id` 重复即重复。
- 非空 `message_id` 重复也视为重复。
- 两个 ID 分开保存和查询，没有拼接。
- `ChatOrchestrator` 在 session 锁外、锁内各检查一次。
- 正常回复、固定校验回复和应用错误回复发送成功后标记完成。

注意：本阶段仍是轻量 `is_duplicate → 执行 → mark_completed` 模式，没有引入 Redis 或原子 claim 状态。

### 4.2 应用异常和错误映射

新增类型化异常：

| 错误码 | 异常 | 用户提示 |
|---|---|---|
| `IDENTITY_NOT_FOUND` | `IdentityNotFoundError` | 未找到您的用户身份，请联系管理员。 |
| `USER_DISABLED` | `UserDisabledError` | 当前用户已被禁用，请联系管理员。 |
| `USER_ROLE_MISSING` | `UserRoleMissingError` | 当前用户未配置采购角色，请联系管理员。 |
| `REQUIREMENT_NOT_FOUND` | `RequirementNotFoundError` | 未找到指定采购单，请确认编号后重试。 |
| `REQUIREMENT_ACCESS_DENIED` | `RequirementAccessDeniedError` | 您无权访问该采购单。 |

处理方式：

- `IdentityService` 转换身份不存在，并校验禁用状态和空角色。
- `RequirementResolver` 转换采购单不存在和不可访问异常。
- `ChatOrchestrator` 捕获已知应用异常，记录包含错误码和事件信息的 warning 日志并发送固定提示。
- 未知异常通过 `logger.exception` 记录后继续抛出。
- 上述错误均不调用 Fake Agent。

### 4.3 消息类型和空文本校验

以下情况在身份解析前直接返回：

- `event_type != TEXT_MESSAGE`
- `text is None`
- 空字符串
- 纯空白文本

固定回复：

```text
当前仅支持文字采购信息，请直接发送文字内容。
```

这些消息不会进入 IdentityService、RequirementResolver 或 Fake Agent，重复投递也不会重复回复。

### 4.4 最小 Bootstrap

新增：

- `ApplicationContainer`
- `build_fake_application()`
- `scripts/demo_fake_pipeline.py`

容器显式组装 Fake Backend、三个 Memory Store、LockManager、Application Services、Fake Agent、Fake Channel 和 ChatOrchestrator，没有使用 DI 框架。

运行演示：

```powershell
python -m pip install -e ".[dev]"
python scripts\demo_fake_pipeline.py
```

预期输出包含：

```text
user_id=1; roles=REQUESTER; requirement_id=101; status=DRAFT; tools=...
```

## 5. 关键改动文件

核心实现：

- `src/buy_agent/application/errors.py`
- `src/buy_agent/application/chat_orchestrator.py`
- `src/buy_agent/application/identity_service.py`
- `src/buy_agent/application/requirement_resolver.py`
- `src/buy_agent/ports/event_store.py`
- `src/buy_agent/adapters/persistence/memory_event_store.py`
- `src/buy_agent/adapters/backend/fake_backend_gateway.py`
- `src/buy_agent/bootstrap/fake_application.py`
- `scripts/demo_fake_pipeline.py`

测试：

- `tests/unit/test_identity_service.py`
- `tests/unit/test_memory_stores.py`
- `tests/integration/test_chat_orchestrator_boundaries.py`
- `tests/integration/test_fake_bootstrap.py`

配置：

- `pyproject.toml` 增加 `extend-exclude = ["docs"]`，避免 Ruff formatter 修改文档内的 Python 示例。

## 6. 已执行验证

最近一次完整结果：

```text
ruff format --check .  → 48 files already formatted
ruff check .           → All checks passed
mypy src               → Success: no issues found in 37 source files
pytest -q               → 44 passed in 0.43s
demo script             → 成功输出 Fake Agent 上下文
git diff --check        → passed
```

重新验证命令：

```powershell
python -m ruff format --check .
python -m ruff check .
python -m mypy src
python -m pytest -q
python scripts\demo_fake_pipeline.py
git diff --check
```

## 7. 当前明确不做

不要在 Task 1.1 中增加：

- Redis Store。
- Store 替换契约测试。
- 原子 claim、processing 或 failed 事件状态。
- 真实 HTTP BackendGateway。
- 数据库或迁移。
- 飞书 SDK、卡片或群聊。
- LLM、真实 ProcurementAgent 工具循环。
- ActionOrchestrator。
- 复杂配置系统或依赖注入框架。

## 8. 接手后的建议步骤

1. 运行 `git status -sb`，确认仍在 `feature/1-1-pre-agent-boundaries` 且改动未丢失。
2. 阅读本交接文档列出的核心实现和测试。
3. 重新运行完整验证命令。
4. 审阅 `git diff`，重点检查错误映射、日志和去重调用点。
5. 若用户要求发布：
   - 先创建 Task 1.1 GitHub Issue；
   - 只暂存本任务文件和本交接文档；
   - 使用 Conventional Commit；
   - 推送当前分支；
   - 创建目标为 `develop` 的 Draft PR；
   - 不自动合并。

建议 Issue 标题：

```text
Harden pre-agent orchestration boundaries
```

建议 Commit：

```text
feat: harden pre-agent orchestration boundaries
```

建议 PR 标题：

```text
feat: harden pre-agent orchestration boundaries
```
