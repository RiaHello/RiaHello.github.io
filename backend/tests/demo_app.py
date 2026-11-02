"""Offline HTTP/browser fixture: fake resume + fake AI, real isolated Redis keys.

Run from backend: TEST_REDIS_URL=redis://127.0.0.1:16379/0 .venv/bin/uvicorn tests.demo_app:app --host 127.0.0.1 --port 8011 --no-access-log --no-proxy-headers
Never deploy this module. No OpenAI call is made.
"""
import asyncio
import os
from uuid import uuid4
from redis.asyncio import Redis
from app.config import Settings
from app.main import create_app
from app.services.rate_limiter import RateLimiter

class DemoAI:
    async def complete(self, resume, body, state):
        await asyncio.sleep(.05)
        return '根据公开简历，这位虚构测试人物参与过示例项目。此回答仅用于离线接口演示。'
    async def stream(self, resume, body, state):
        answer = await self.complete(resume, body, state)
        for i in range(0,len(answer),8):
            await asyncio.sleep(.03)
            yield 'delta', answer[i:i+8]
        yield 'done', answer

settings=Settings('offline-not-a-real-key','offline-demo-model','offline-test-secret-'*3)
redis=Redis.from_url(os.getenv('TEST_REDIS_URL','redis://127.0.0.1:16379/0'),socket_timeout=2,socket_connect_timeout=2)
limiter=RateLimiter(redis,settings.hmac_secret,'test-browser:'+uuid4().hex)
app=create_app(settings=settings,limiter=limiter,ai=DemoAI(),resume='虚构测试人物；这不是网站主人的真实经历。参与了用于测试的示例项目。'*8)
