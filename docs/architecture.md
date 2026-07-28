# buy-agent 架构设计

## 1. 架构目标

`buy-agent` 需要满足：

- 当前接入飞书私聊；
- 后续可扩展到 Web、钉钉和企业微信；
- Agent 核心不依赖具体消息渠道；
- Agent 不直接依赖数据库和真实 HTTP 接口；
- Mock 后端和真实后端可以替换；
- 同一用户多轮对话可靠隔离；
- 卡片动作走确定性业务流程。

---

## 2. 总体架构

```text
飞书 / Web / 钉钉 / 企业微信
              ↓
       Channel Adapter
              ↓
         InboundEvent
              ↓
      ChatOrchestrator
              ↓
 Identity / Session / Resolver
              ↓
        ContextBuilder
              ↓
          ToolPolicy
              ↓
     ProcurementAgent
              ↓
         ToolRegistry
              ↓
        BackendGateway
              ↓
MockBackendGateway / HttpBackendGateway
```

卡片操作：

```text
渠道卡片回调
→ ActionCommand
→ ActionOrchestrator
→ BackendGateway
→ 更新卡片
→ 通知下一处理人
```

---

## 3. 推荐目录

```text
buy-agent/
├── src/
│   └── buy_agent/
│       ├── bootstrap/
│       ├── domain/
│       ├── application/
│       ├── agent/
│       ├── ports/
│       ├── adapters/
│       │   ├── channels/
│       │   ├── backend/
│       │   ├── persistence/
│       │   └── llm/
│       └── tools/
├── tests/
├── docs/
├── .github/
├── .env.example
├── pyproject.toml
├── README.md
└── AGENTS.md
```

按开发阶段创建文件，不一次性创建空目录。

---

## 4. 分层职责

### `bootstrap/`

负责：

- 读取配置；
- 创建依赖；
- 选择 Mock 或 HTTP 后端；
- 选择内存或 Redis 存储；
- 注册渠道处理器；
- 启动应用。

### `domain/`

负责定义：

- 渠道枚举；
- 用户身份；
- 统一事件；
- 会话状态；
- 采购上下文；
- 卡片动作；
- Agent 输出；
- 工具结果；
- 统一异常。

不得调用外部 SDK。

### `application/`

负责业务编排：

- `ChatOrchestrator`
- `ActionOrchestrator`
- `IdentityService`
- `SessionService`
- `RequirementResolver`
- `ContextBuilder`
- `ToolPolicy`
- `NotificationService`

不负责自然语言理解，不直接调用飞书 SDK。

### `agent/`

负责：

- 构建 Prompt；
- 调用模型；
- 处理 `tool_calls`；
- 执行受控工具；
- 解析最终输出。

当前只有一个 `ProcurementAgent`。

### `ports/`

定义核心层依赖的接口：

- `ChannelPort`
- `BackendGateway`
- `SessionStore`
- `MessageStore`
- `EventStore`
- `LockManager`
- `LLMClient`

### `adapters/`

实现外部能力：

- 飞书消息解析与发送；
- Mock/HTTP 后端；
- 内存/Redis 存储；
- 模型 API。

### `tools/`

封装 Agent 能调用的业务能力。

工具只调用 `BackendGateway`，不能直接访问数据库或 HTTP。

---

## 5. 渠道扩展

核心层统一使用：

```python
@dataclass(frozen=True)
class ExternalIdentity:
    channel: ChannelType
    external_tenant_id: str
    external_user_id: str
```

```python
@dataclass(frozen=True)
class InboundEvent:
    event_id: str
    message_id: str | None
    event_type: InboundEventType
    identity: ExternalIdentity
    conversation_id: str
    text: str | None
    action: dict | None
    raw_payload: dict
```

各渠道只实现：

```text
event_parser
handler
renderer
sender
```

禁止复制一套新的采购 Agent。

---

## 6. 会话设计

会话键：

```text
procurement:<channel>:<external_tenant_id>:<external_user_id>
```

不同渠道的 Memory 默认隔离，正式采购记录共享。

Memory 保存：

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

正式业务事实以后端为准。

---

## 7. 当前采购单解析

`RequirementResolver` 按以下优先级确定采购单：

1. 用户明确提供采购编号或 ID；
2. `session.active_requirement_id`；
3. 当前用户唯一一条未完成采购单；
4. 多条未完成采购单时要求用户选择；
5. 没有采购单时允许创建草稿。

不得让模型猜测采购单。

---

## 8. 并发与可靠性

- 同一 `session_key` 使用独立锁；
- 不同用户并行；
- `event_id`、`message_id` 用于消息去重；
- `action_token` 用于卡片幂等；
- 关键业务状态最终由后端校验；
- Agent 侧的 Tool Policy 只做前置过滤。

---

## 9. 依赖注入

开发环境：

```text
BackendGateway → MockBackendGateway
SessionStore → MemorySessionStore
MessageStore → MemoryMessageStore
EventStore → MemoryEventStore
LockManager → LocalLockManager
```

联调环境：

```text
BackendGateway → HttpBackendGateway
```

正式多实例部署时再增加 Redis 实现。

---

## 10. 当前不实现

- Agent Router；
- 多角色 Agent；
- 群聊；
- OCR；
- 图片字段提取；
- 真实数据库；
- 未确认的 HTTP API；
- 钉钉、微信和 Web 的具体实现。
