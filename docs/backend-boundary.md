# 后端职责边界

## 1. 本仓库负责

```text
消息渠道接入
统一事件转换
飞书文本与卡片
会话与Memory
ContextBuilder
RequirementResolver
ToolPolicy
ProcurementAgent
ToolRegistry和Tools
BackendGateway抽象
MockBackendGateway
消息去重与用户级锁
Agent侧测试
```

---

## 2. 后端同事负责

```text
用户、角色、部门和权限范围
采购需求正式数据
采购状态机
字段完整性最终校验
白名单和历史采购数据
供应商档案
供应商黑名单
数据库事务
乐观锁
后端幂等
审计日志
正式HTTP API
```

---

## 3. 双方共同原则

### Agent 侧

负责：

- 理解用户表达；
- 提取候选字段；
- 选择允许的工具；
- 组织追问；
- 展示推荐；
- 调用后端能力。

### 后端侧

负责：

- 最终身份与权限校验；
- 最终状态校验；
- 最终字段校验；
- 正式数据保存；
- 事务和并发冲突处理；
- 审计与幂等。

即使 Tool Policy 已过滤工具，后端仍必须再次校验。

---

## 4. 身份边界

渠道适配器获取：

```text
飞书 open_id
钉钉 userId/staffId
企业微信 userId
Web 登录用户
```

核心层统一为：

```text
ExternalIdentity
```

后端将外部身份解析成：

```text
CurrentPrincipal
```

`CurrentPrincipal` 至少包含：

```text
user_id
name
roles
department_ids
data_scopes
system_status
```

Agent 不允许自行推断角色。

---

## 5. 通知边界

后端返回业务处理结果和下一处理人。

渠道通知由本仓库负责。

建议后端返回内部用户 ID，本仓库通过渠道地址映射完成飞书推送。

具体通知接口等待双方确认。
