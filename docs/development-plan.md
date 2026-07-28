# 开发计划

## Phase 1：项目骨架

目标：

- 建立 `src` 布局；
- 配置 Pydantic Settings；
- 日志与 Trace；
- 统一异常；
- GitHub CI；
- 基础领域模型和 Ports。

完成标准：

```text
项目可安装
测试可运行
CI可执行
无业务实现
```

---

## Phase 2：会话与可靠性基础

实现：

```text
MemorySessionStore
MemoryMessageStore
MemoryEventStore
LocalLockManager
session_key
event_id/message_id去重
```

完成标准：

```text
同一用户串行
不同用户并行
Memory隔离
重复事件被过滤
```

---

## Phase 3：MockBackendGateway

实现：

```text
模拟用户和角色
模拟采购需求
模拟字段保存
模拟推荐
模拟供应商
模拟版本号
模拟错误码
模拟状态操作
```

完成标准：

```text
不依赖真实后端即可运行工具测试
```

---

## Phase 4：Context 与工具策略

实现：

```text
IdentityService
SessionService
RequirementResolver
ContextBuilder
ToolPolicy
```

完成标准：

```text
能为单次Agent调用构造完整上下文
只返回当前允许工具
```

---

## Phase 5：Agent 核心

实现：

```text
LLMClient
LLMResponse
ToolCall
ToolResult
ToolRegistry
PromptBuilder
ResponseParser
ProcurementAgent
```

完成标准：

```text
Fake LLM下可以完成多轮工具调用
未注册工具会被阻止
最大轮数生效
```

---

## Phase 6：需求人流程

实现：

```text
create_requirement_draft
save_requester_fields
recommend_device_types
recommend_brands
recommend_models
submit_for_review
cancel_requirement
```

完成标准：

```text
从自然语言到确认提交完整跑通
```

---

## Phase 7：飞书接入

实现：

```text
FeishuEventParser
FeishuHandler
FeishuRenderer
FeishuSender
ActionOrchestrator
```

完成标准：

```text
飞书私聊可完成需求人模拟流程
卡片按钮不调用LLM
```

---

## Phase 8：其余角色

顺序：

```text
REVIEWER
→ PURCHASER
→ WAREHOUSE
```

不要同时并行开发三个角色。

---

## Phase 9：可靠性完善

实现：

```text
卡片幂等
模型超时
Mock后端失败
错误提示
并发测试
集成测试
日志脱敏
```

---

## Phase 10：后端联调

双方冻结：

```text
HTTP方法
URL
鉴权
请求和响应Schema
错误码
状态
版本号
幂等字段
通知地址
```

随后实现：

```text
HttpBackendGateway
真实契约测试
错误码映射
```

不重写 Agent、Context、Tool Policy 和工具接口。
