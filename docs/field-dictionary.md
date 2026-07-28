# 字段、角色与状态字典

> 当前用于 Agent、Mock 和双方讨论。  
> 状态与字段最终需要和后端负责人确认。

## 1. 角色

| 角色值 | 中文名称 | 主要职责 |
|---|---|---|
| `REQUESTER` | 需求人 | 创建和提交采购需求 |
| `REVIEWER` | 楼长/审核人 | 审批并补充供应商与商务信息 |
| `PURCHASER` | 采购员 | 补充供应商财务与合同信息 |
| `WAREHOUSE` | 仓库管理员 | 填写库位并确认入库 |

用户可以拥有多个角色。

---

## 2. 需求人字段

| 字段 | 中文名称 | 类型 | 必填 |
|---|---|---:|---:|
| `device_type` | 设备类型 | string | 是 |
| `product_name` | 具体设备名称 | string | 是 |
| `quantity` | 数量 | integer | 是 |
| `brand` | 品牌 | string | 是 |
| `model` | 型号 | string | 是 |
| `reason` | 需求原因 | string | 是 |

默认追问顺序：

```text
device_type
→ product_name
→ quantity
→ brand
→ model
→ reason
```

---

## 3. 楼长字段

| 字段 | 中文名称 | 类型 | 必填 |
|---|---|---:|---:|
| `price` | 价格 | decimal/string | 是 |
| `supplier_id` | 供应商ID | integer | 是 |
| `supplier_contact` | 供应商联系方式/链接 | string | 是 |
| `need_contract` | 是否需要合同 | boolean | 是 |
| `contract_type` | 合同类型 | string | 条件必填 |
| `payment_method` | 付款方式 | string | 是 |
| `delivery_date` | 到货时间 | date | 是 |
| `warranty` | 质保 | string | 是 |

条件：

```text
need_contract = true
→ contract_type 必填
```

---

## 4. 采购员字段

| 字段 | 中文名称 | 类型 | 必填 |
|---|---|---:|---:|
| `supplier_tax_number` | 供应商税号 | string | 是 |
| `bank_name` | 开户行 | string | 是 |
| `bank_account` | 银行账号 | string | 是 |
| `address` | 地址 | string | 是 |
| `contract_contact` | 合同联系方式 | string | 是 |
| `project_tax_rate` | 项目税率 | decimal/string | 是 |

`bank_account` 属于敏感字段，日志中必须脱敏。

---

## 5. 仓库字段

| 字段 | 中文名称 | 类型 | 必填 |
|---|---|---:|---:|
| `warehouse_location` | 仓库位置 | string | 是 |
| `warehouse_note` | 备注 | string | 否 |

---

## 6. 当前模拟状态

```text
DRAFT
READY_TO_SUBMIT
PENDING_REVIEW
REVIEW_FILLING
READY_FOR_PURCHASER
PURCHASER_FILLING
READY_FOR_WAREHOUSE
PENDING_WAREHOUSE
COMPLETED
REJECTED
CANCELLED
```

模拟主流程：

```text
DRAFT
→ READY_TO_SUBMIT
→ PENDING_REVIEW
→ REVIEW_FILLING
→ READY_FOR_PURCHASER
→ PURCHASER_FILLING
→ READY_FOR_WAREHOUSE
→ PENDING_WAREHOUSE
→ COMPLETED
```

分支：

```text
PENDING_REVIEW → REJECTED
DRAFT/READY_TO_SUBMIT → CANCELLED
```

这些状态当前只服务于 Mock 和 Tool Policy，不代表正式后端已经采用。

---

## 7. 卡片动作

```text
submit_for_review
approve_requirement
reject_requirement
submit_to_purchaser
submit_to_warehouse
complete_warehouse_entry
cancel_requirement
```

按钮负载至少包含：

```json
{
  "action": "submit_for_review",
  "requirement_id": 101,
  "requirement_version": 3,
  "action_token": "uuid"
}
```
