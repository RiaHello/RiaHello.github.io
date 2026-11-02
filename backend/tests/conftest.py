from contextlib import asynccontextmanager
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import httpx
import pytest
from app.config import Settings
from app.main import create_app
from app.services.ai_client import AIClient

RESUME = '虚构测试简历；测试人物在示例学校学习，并在示例项目参与开发。' * 8
SETTINGS = Settings('test-secret-key-never-real', 'test-model', 'test-hmac-secret-' * 4)

def response(text='根据公开简历，参与过示例项目。', status='completed', **kwargs):
    return NS(status=status, output=[NS(type='message', status='completed', content=[NS(type='output_text', text=text)])], usage=None, **kwargs)

class FakeLimiter:
    def __init__(self): self.ip_calls = self.daily_calls = 0
    async def check_ip(self, ip): self.ip_calls += 1
    async def reserve_daily(self): self.daily_calls += 1
    async def ready(self): return True

@asynccontextmanager
async def harness(*, resume=RESUME, limiter=None, sdk_response=None):
    limiter = limiter or FakeLimiter()
    ai = AIClient(SETTINGS)
    ai.sdk.responses.create = AsyncMock(return_value=sdk_response or response())
    app = create_app(settings=SETTINGS, limiter=limiter, ai=ai, resume=resume)
    try:
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                yield NS(client=client, app=app, ai=ai, limiter=limiter)
    finally:
        await ai.close()

@pytest.fixture
def rig(): return harness
