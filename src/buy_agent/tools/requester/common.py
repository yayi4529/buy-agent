from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel


class ActionTokenFactory(Protocol):
    def create(self) -> str: ...


class UUIDActionTokenFactory:
    def create(self) -> str:
        return str(uuid4())


class RequesterTool:
    name: str
    description: str
    arguments_model: type[BaseModel]

    def definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.arguments_model.model_json_schema(),
        }
