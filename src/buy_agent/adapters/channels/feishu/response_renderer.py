from typing import Any

from buy_agent.domain.agent import AgentResponse
from buy_agent.domain.interaction import InteractionAction, InteractionView
from buy_agent.ports.channel import RenderedInteraction


class FeishuResponseRenderer:
    def render_text(self, response: AgentResponse) -> str:
        return response.text.strip() or (
            response.interaction.fallback_text
            if response.interaction and response.interaction.fallback_text
            else response.interaction.title
            if response.interaction
            else "暂时无法生成回复，请稍后重试。"
        )

    def render_interaction(self, view: InteractionView) -> RenderedInteraction:
        elements: list[dict[str, Any]] = []
        for field in view.fields:
            if field.value:
                elements.append(
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**{field.label}**：{field.value}",
                        },
                    }
                )
        elements.append(
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "确认后将提交采购申请。"},
            }
        )
        if view.selection_groups:
            group = view.selection_groups[0]
            for option in group.options:
                for action in view.actions:
                    elements.append(
                        {
                            "tag": "action",
                            "actions": [
                                _button(
                                    action,
                                    extra={group.name: option.value},
                                    label=f"由{option.label}处理并提交",
                                )
                            ],
                        }
                    )
        elif view.actions:
            elements.append(
                {"tag": "action", "actions": [_button(action) for action in view.actions]}
            )
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "blue",
                "title": {"tag": "plain_text", "content": "采购申请确认"},
            },
            "elements": elements,
        }
        return RenderedInteraction(card, view.fallback_text or view.title)


def _button(
    action: InteractionAction,
    *,
    extra: dict[str, object] | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    payload = {
        "action": "SUBMIT_REQUEST",
        "action_token": action.payload.get("action_token"),
        "conversation_id": action.payload.get("conversation_id"),
        "expected_state_version": action.payload.get("expected_state_version"),
    }
    if extra:
        payload.update(extra)
    return {
        "tag": "button",
        "type": "primary",
        "text": {"tag": "plain_text", "content": label or action.label},
        "value": payload,
    }
