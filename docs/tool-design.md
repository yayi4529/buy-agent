# Agent 工具设计

## 1. 设计原则

- 当前只有一个 `ProcurementAgent`；
- 工具按角色分目录，不代表多个 Agent；
- 每个工具只完成一个明确动作；
- 工具只能通过 `BackendGateway` 操作业务；
- 工具不能直接访问数据库；
- 工具不能直接写 HTTP URL；
- 只向模型注册本轮允许的工具；
- 后端负责最终权限和状态校验。

---

## 2. 工具基础接口

```python
class AgentTool(Protocol):
    name: str
    description: str
    schema: dict[str, Any]

    async def execute(
        self,
        arguments: dict[str, Any],
        execution_context: ToolExecutionContext,
    ) -> ToolResult:
        ...
```

程序注入的执行上下文：

```text
principal
user_id
session_key
channel
tenant_id
trace_id
```

禁止模型提供这些字段。

---

## 3. ToolResult

建议统一为：

```python
@dataclass(frozen=True)
class ToolResult:
    success: bool
    code: str
    message: str
    data: dict[str, Any] | None = None
```

Agent 根据 `code` 处理业务失败，不解析异常堆栈。

---

## 4. 工具分组

### 公共工具

```text
get_requirement_detail
get_my_tasks
query_purchase_records
```

### 需求人工具

```text
create_requirement_draft
save_requester_fields
recommend_device_types
recommend_brands
recommend_models
submit_for_review
cancel_requirement
```

### 楼长工具

```text
approve_requirement
reject_requirement
save_reviewer_fields
recommend_suppliers
recommend_supplier_contacts
blacklist_supplier
submit_to_purchaser
```

### 采购员工具

```text
query_supplier_profile
save_purchaser_fields
submit_to_warehouse
```

### 仓库工具

```text
save_warehouse_fields
complete_warehouse_entry
```

---

## 5. Tool Policy

本轮工具：

```text
角色工具 ∩ 状态工具
```

示例角色矩阵：

```python
ROLE_TOOLS = {
    "REQUESTER": {
        "create_requirement_draft",
        "get_requirement_detail",
        "save_requester_fields",
        "recommend_device_types",
        "recommend_brands",
        "recommend_models",
        "submit_for_review",
        "cancel_requirement",
        "query_purchase_records",
    },
    "REVIEWER": {
        "get_requirement_detail",
        "approve_requirement",
        "reject_requirement",
        "save_reviewer_fields",
        "recommend_suppliers",
        "recommend_supplier_contacts",
        "blacklist_supplier",
        "submit_to_purchaser",
        "query_purchase_records",
    },
    "PURCHASER": {
        "get_requirement_detail",
        "query_supplier_profile",
        "save_purchaser_fields",
        "submit_to_warehouse",
        "query_purchase_records",
    },
    "WAREHOUSE": {
        "get_requirement_detail",
        "save_warehouse_fields",
        "complete_warehouse_entry",
        "query_purchase_records",
    },
}
```

状态矩阵当前服务于 Mock，正式状态待后端确认。

---

## 6. 推荐工具

推荐工具必须返回稳定 ID 和展示字段。

模型最多展示 3 条。

会话保存：

```text
last_recommendations
```

当用户回复“第一个”时，通过最近推荐列表映射成明确 ID 或型号，再调用保存工具。

推荐结果不能自动写入采购需求，必须经过用户确认。

---

## 7. 明确动作工具

以下操作通常由卡片按钮触发，不经过 LLM：

```text
submit_for_review
approve_requirement
reject_requirement
submit_to_purchaser
submit_to_warehouse
complete_warehouse_entry
cancel_requirement
```

对应逻辑由 `ActionOrchestrator` 调用 `BackendGateway.execute_action`。

---

## 8. 工具错误

至少处理：

```text
USER_NOT_FOUND
USER_DISABLED
PERMISSION_DENIED
REQUIREMENT_NOT_FOUND
INVALID_STATUS
MISSING_REQUIRED_FIELDS
CONCURRENT_MODIFICATION
SUPPLIER_NOT_FOUND
SUPPLIER_BLACKLISTED
DUPLICATE_OPERATION
VALIDATION_ERROR
BACKEND_TIMEOUT
BACKEND_UNAVAILABLE
INTERNAL_ERROR
```

不得把技术堆栈直接返回用户。
