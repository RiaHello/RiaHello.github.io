from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator


def normalize(value: str, maximum: int) -> str:
    value = value.strip()
    if not 1 <= len(value) <= maximum:
        raise ValueError('length')
    if any((ord(c) < 32 and c not in '\n\t') or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError('control character')
    return value

class Message(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    role: Literal['user', 'assistant']
    content: StrictStr

    @model_validator(mode='after')
    def clean(self):
        self.content = normalize(self.content, 1000 if self.role == 'user' else 2000)
        return self

class ChatRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    question: StrictStr
    history: list[Message] = Field(default_factory=list)

    @field_validator('question')
    @classmethod
    def clean_question(cls, value):
        return normalize(value, 1000)

    @field_validator('history')
    @classmethod
    def check_history(cls, history):
        if len(history) not in (0, 2, 4, 6): raise ValueError('round count')
        if any(m.role != ('user' if i % 2 == 0 else 'assistant') for i, m in enumerate(history)):
            raise ValueError('role order')
        if sum(len(m.content) for m in history) > 6000: raise ValueError('total length')
        return history
