# 测试规范

## 1. 测试目录

```text
tests/
├── unit/
├── integration/
├── contract/
└── concurrency/
```

当前真实后端接口未冻结，契约测试先覆盖内部 `BackendGateway` 行为和 Mock 实现。

---

## 2. 单元测试

至少覆盖：

```text
build_session_key
InboundEvent解析
ActionCommand解析
ToolPolicy
RequirementResolver
ContextBuilder
ToolRegistry
推荐序号解析
InteractionView渲染
EventStore去重
action_token幂等
错误码映射
```

---

## 3. Agent 测试

使用 Fake LLM 或脚本化 LLM，不依赖真实在线模型。

至少测试：

- 无工具调用时返回文本；
- 单次工具调用；
- 多轮工具调用；
- 调用未注册工具；
- 工具返回业务失败；
- 达到最大轮数；
- “第一个”映射最近推荐；
- 一次只追问一个字段；
- 不虚构保存成功。

---

## 4. 集成测试

### 需求人

```text
输入：我要采购5台华为交换机，用于网络扩容
→ 创建草稿
→ 保存已有字段
→ 只追问缺失型号
→ 返回最多3个推荐
→ 用户选择第一个
→ 保存型号
→ 生成确认交互
→ 提交后进入PENDING_REVIEW（Mock）
```

### 楼长

```text
审批通过
→ 补充商务字段
→ 推荐供应商
→ 提交采购员
```

### 采购员

```text
查询供应商资料
→ 保存采购员字段
→ 提交仓库
```

### 仓库

```text
填写库位与备注
→ 确认入库
→ Mock状态为COMPLETED
```

---

## 5. 并发测试

必须证明：

- 同一用户连续 3 条消息严格串行；
- 两个用户同时处理；
- 用户 A 和 B 的 Memory 不串；
- 不使用全局锁；
- 锁释放后后续消息可继续处理。

---

## 6. 幂等测试

### 消息

相同 `event_id` 或 `message_id` 重复投递：

```text
Agent只执行一次
后端工具只调用一次
回复不重复发送
```

### 卡片

相同 `action_token` 重复点击：

```text
业务动作只执行一次
不重复推送下一角色
返回已处理提示
```

---

## 7. 错误测试

至少覆盖：

```text
用户不存在
用户被禁用
无角色
无权限
采购单不存在
多条采购单未指定
状态不允许
缺失字段
供应商黑名单
版本冲突
重复操作
模型超时
Mock后端异常
Agent达到最大轮数
```

---

## 8. CI

建议执行：

```bash
ruff format --check .
ruff check .
mypy src
pytest -q
```

PR 未通过 CI 不得合并。
