# 后端接口未冻结时的独立开发范围

## 1. 目标

在没有真实后端 HTTP API 的情况下，独立完成：

```text
统一事件
会话与并发
Context
Tool Policy
ProcurementAgent
Tools
MockBackendGateway
飞书消息与卡片
单元、集成和并发测试
```

---

## 2. 当前可开发

### Agent 核心

```text
LLMClient接口
LLMResponse/ToolCall模型
PromptBuilder
ProcurementAgent工具循环
ResponseParser
ToolRegistry
ToolResult
```

### 应用编排

```text
ChatOrchestrator
ActionOrchestrator
IdentityService
SessionService
RequirementResolver
ContextBuilder
ToolPolicy
NotificationService
```

### 会话与可靠性

```text
MemorySessionStore
MemoryMessageStore
MemoryEventStore
LocalLockManager
event_id/message_id去重
action_token幂等
```

### Mock 后端

```text
模拟用户和角色
模拟采购需求
模拟字段保存
模拟推荐
模拟供应商
模拟状态变化
模拟版本冲突和业务错误
```

### 飞书

```text
私聊文本解析
文本回复
通用交互视图
飞书卡片渲染
卡片回调
主动推送
```

---

## 3. 当前禁止实现

- 猜测正式 HTTP URL；
- 将 Mock Schema 当成正式接口；
- Tool 直接调用 HTTP；
- Agent 连接 MySQL；
- 创建数据库迁移；
- 创建 Agent Router；
- 创建四个角色 Agent；
- 实现 OCR；
- 实现群聊；
- 实现未要求的钉钉、微信和 Web 入口；
- 大量创建未来空文件。

---

## 4. 推荐开发顺序

```text
Phase 1  项目骨架、配置、领域模型和Ports
Phase 2  会话存储、消息存储、去重和用户级锁
Phase 3  MockBackendGateway
Phase 4  RequirementResolver、ContextBuilder和ToolPolicy
Phase 5  ToolRegistry和ProcurementAgent
Phase 6  需求人模拟流程
Phase 7  飞书文本和卡片
Phase 8  楼长、采购员和仓库流程
Phase 9  并发、幂等和异常测试
Phase 10 后端接口冻结后实现HttpBackendGateway
```

---

## 5. 第一批建议 Issue

```text
#1 Initialize project skeleton
#2 Add settings, logging and errors
#3 Define event and identity models
#4 Define BackendGateway and storage ports
#5 Implement in-memory stores
#6 Implement per-session lock
#7 Implement MockBackendGateway
#8 Implement RequirementResolver
#9 Implement ContextBuilder
#10 Implement ToolPolicy
#11 Implement ToolRegistry
#12 Implement ProcurementAgent loop
#13 Implement requester mock flow
#14 Implement InteractionView
#15 Implement Feishu event parser and sender
#16 Implement Feishu card renderer
#17 Implement ActionOrchestrator
#18 Add idempotency tests
#19 Add concurrency tests
#20 Implement reviewer mock flow
#21 Implement purchaser mock flow
#22 Implement warehouse mock flow
#23 Add CI
```

优先完成 `#1` 到 `#13`，先跑通需求人模拟流程。

---

## 6. 独立开发完成标准

```text
ProcurementAgent可以调用受控工具
MockBackendGateway支撑四角色流程
同一用户消息串行
不同用户消息并行
Memory不串
重复事件不重复调用Agent
重复卡片不重复执行
卡片动作不调用LLM
核心代码不依赖飞书SDK
工具不直接访问HTTP或数据库
测试与CI通过
```
