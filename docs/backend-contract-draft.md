# 后端能力契约草案

> 状态：草案，尚未与后端负责人确认。  
> 本文件只描述 Agent 需要的业务能力，不固定 HTTP 方法、URL、鉴权和最终字段。

## 1. 当前原则

- Agent 和 Tool 只依赖 `BackendGateway`；
- 当前使用 `MockBackendGateway`；
- 不在核心代码中写真实 URL；
- 正式接口确认后，只修改 `HttpBackendGateway` 和契约测试；
- Mock 数据结构不代表后端数据库设计。

---

## 2. 身份解析

能力名：

```text
resolve_identity
```

输入：

```text
channel
external_tenant_id
external_user_id
```

返回：

```text
user_id
name
roles
department_ids
data_scopes
system_status
```

待确认：

- 未同步用户如何处理；
- 是否自动同步通讯录；
- 服务间鉴权方式；
- 用户禁用的错误码。

---

## 3. 查询当前任务

能力名：

```text
list_active_requirements
```

输入：

```text
current principal
可选角色
可选状态
```

返回：

```text
当前用户有权处理的未完成采购需求列表
```

待确认：

- 分页方式；
- 数据权限规则；
- “当前任务”和“历史记录”是否使用同一接口。

---

## 4. 创建采购草稿

能力名：

```text
create_requirement_draft
```

返回：

```text
requirement_id
requirement_no
status
version
```

待确认：

- 是否允许多个草稿；
- 是否复用现有草稿；
- 编号生成规则。

---

## 5. 获取采购详情

能力名：

```text
get_requirement
```

需要返回：

```text
采购编号
当前状态
版本号
四角色字段
缺失字段
下一个缺失字段
允许动作
当前处理人
```

---

## 6. 保存角色字段

能力名：

```text
save_requester_fields
save_reviewer_fields
save_purchaser_fields
save_warehouse_fields
```

通用输入：

```text
requirement_id
fields
expected_version
current principal
```

通用返回：

```text
最新采购上下文
最新版本号
缺失字段
下一个缺失字段
当前状态
```

待确认：

- 是否支持部分更新；
- 空值是忽略还是清空；
- 字段验证错误格式；
- 条件必填规则由哪一层返回。

---

## 7. 执行业务动作

能力名：

```text
execute_action
```

动作：

```text
submit_for_review
approve_requirement
reject_requirement
submit_to_purchaser
submit_to_warehouse
complete_warehouse_entry
cancel_requirement
blacklist_supplier
```

输入：

```text
action
requirement_id
expected_version
action_token
payload
current principal
```

返回：

```text
最新状态
最新版本号
处理结果
下一处理人
通知所需信息
```

待确认：

- 幂等字段；
- 版本冲突错误；
- 驳回后状态；
- 下一处理人分配规则。

---

## 8. 推荐查询

能力名：

```text
query_recommendations
```

类型：

```text
device_types
brands
models
suppliers
supplier_contacts
supplier_finance_profile
```

要求：

- 返回最多由调用方指定数量；
- 供应商推荐排除黑名单；
- 返回稳定的推荐项 ID；
- Agent 只展示最多 3 条。

---

## 9. 供应商档案

能力名：

```text
query_supplier_profile
```

待确认：

- 各角色可见字段；
- 银行账号脱敏规则；
- 敏感字段日志规则；
- 查询审计要求。

---

## 10. 采购记录查询

能力名：

```text
query_purchase_records
```

建议支持的结构化过滤条件：

```text
requirement_no
status
device_type
brand
model
supplier_id
created_from
created_to
page
page_size
```

不得允许模型直接生成任意 SQL。

---

## 11. 待双方冻结的内容

```text
HTTP方法
URL
鉴权方式
请求Schema
响应Schema
统一错误码
日期格式
金额格式
税率格式
版本字段
幂等字段
超时与重试
下一处理人返回方式
```
