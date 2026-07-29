from typing import Any

from buy_agent.domain.action import ActionResult, ActionResultStatus
from buy_agent.ports.channel import RenderedInteraction


class FeishuActionResultRenderer:
    def render(self, result: ActionResult) -> RenderedInteraction:
        status = result.status
        if status in {ActionResultStatus.SUCCESS, ActionResultStatus.ALREADY_COMPLETED}:
            title, template = "采购申请已提交", "green"
            message = result.message or "提交成功"
        elif status is ActionResultStatus.IN_PROGRESS:
            title, template, message = "正在处理中", "blue", "正在处理中，请勿重复提交。"
        elif status is ActionResultStatus.VERSION_CONFLICT:
            title, template = "采购信息已变化", "orange"
            message = "采购信息已发生变化，请返回对话重新确认。"
        elif status is ActionResultStatus.PERMISSION_DENIED:
            title, template = "无权操作", "red"
            message = "当前身份无权执行此操作。"
        elif status is ActionResultStatus.VALIDATION_ERROR:
            title, template = "信息校验失败", "orange"
            message = "提交信息不完整，请返回对话重新确认。"
        elif status is ActionResultStatus.BUSINESS_ERROR:
            title, template = "提交失败", "orange"
            message = "采购申请暂未提交，请返回对话重新确认。"
        else:
            title, template = "系统暂时不可用", "red"
            message = f"操作未完成，请稍后重试。问题编号：{result.code}"
        elements: list[dict[str, Any]] = [
            {"tag": "div", "text": {"tag": "lark_md", "content": message}}
        ]
        if result.interaction is not None and status in {
            ActionResultStatus.SUCCESS,
            ActionResultStatus.ALREADY_COMPLETED,
        }:
            elements.extend(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**{field.label}**：{field.value}",
                    },
                }
                for field in result.interaction.fields
                if field.value
            )
        return RenderedInteraction(
            {
                "config": {"wide_screen_mode": True},
                "header": {
                    "template": template,
                    "title": {"tag": "plain_text", "content": title},
                },
                "elements": elements,
            },
            message,
        )
