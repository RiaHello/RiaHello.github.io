import asyncio
import os
from pathlib import Path
from uuid import uuid4
import pytest
from redis.asyncio import Redis
from app.config import Settings, ConfigurationError
from app.services.resume_loader import load_resume, RESUME_PATH
from app.services.rate_limiter import RateLimiter
from app.errors import AppError
from .conftest import SETTINGS

@pytest.mark.parametrize('data,valid', [(b'a'*99,False),(b'a'*100,True),(b'a'*12000,True),(b'a'*12001,False),(b' '*65537,False),(b'\xff'*100,False),('汉'*100,True)])
def test_resume_validation(tmp_path,data,valid):
    path=tmp_path/'test.md'
    path.write_bytes(data.encode() if isinstance(data,str) else data)
    assert (load_resume(path) is not None)==valid

def test_missing_unreadable_and_cwd(tmp_path,monkeypatch):
    assert load_resume(tmp_path/'missing') is None
    assert load_resume(tmp_path) is None
    monkeypatch.chdir(tmp_path)
    assert RESUME_PATH.is_absolute() and RESUME_PATH.name=='public_resume.md'
    # Capture which path default loader opens, without creating the real private file.
    seen=[]
    original=Path.open
    def intercepted(self,*args,**kwargs):
        seen.append(self)
        if self==RESUME_PATH: raise PermissionError()
        return original(self,*args,**kwargs)
    monkeypatch.setattr(Path,'open',intercepted)
    assert load_resume() is None and seen==[RESUME_PATH]

def test_configuration_strict_and_secret_safe(monkeypatch):
    for field in ('DEEPSEEK_API_KEY','DEEPSEEK_MODEL','RATE_LIMIT_HMAC_SECRET','APP_ENV','ALLOWED_ORIGINS'):
        monkeypatch.delenv(field,raising=False)
    with pytest.raises(ConfigurationError) as exc: Settings.from_env()
    assert str(exc.value)=='DEEPSEEK_API_KEY,DEEPSEEK_MODEL,RATE_LIMIT_HMAC_SECRET'
    monkeypatch.setenv('DEEPSEEK_API_KEY','SECRET_KEY')
    monkeypatch.setenv('DEEPSEEK_MODEL','test-model')
    monkeypatch.setenv('RATE_LIMIT_HMAC_SECRET','s'*32)
    assert Settings.from_env().origins==SETTINGS.origins
    monkeypatch.setenv('APP_ENV','production')
    with pytest.raises(ConfigurationError): Settings.from_env()
    for origin in ('*','https://test.example/path','https://user:pass@test.example','null','https://test.example:bad'):
        monkeypatch.setenv('ALLOWED_ORIGINS',origin)
        with pytest.raises(ConfigurationError) as exc: Settings.from_env()
        assert str(exc.value)=='ALLOWED_ORIGINS'
    monkeypatch.setenv('ALLOWED_ORIGINS','https://test.example')
    assert Settings.from_env().app_env=='production'
    monkeypatch.setenv('RATE_LIMIT_HMAC_SECRET','汉'*32)
    with pytest.raises(ConfigurationError) as exc: Settings.from_env()
    assert str(exc.value)=='RATE_LIMIT_HMAC_SECRET'

@pytest.fixture
async def real_limiter():
    url=os.getenv('TEST_REDIS_URL')
    if not url: pytest.skip('real Redis not configured; set TEST_REDIS_URL')
    redis=Redis.from_url(url,socket_timeout=2,socket_connect_timeout=2)
    await redis.ping()
    prefix='test-resume:'+uuid4().hex
    limiter=RateLimiter(redis,SETTINGS.hmac_secret,prefix)
    try: yield limiter
    finally:
        keys=[key async for key in redis.scan_iter(match=prefix+':*')]
        if keys: await redis.delete(*keys)
        await redis.aclose()

@pytest.mark.redis
async def test_real_redis_minute_day_and_hmac_ttl(real_limiter):
    limiter=real_limiter
    # Fixed injected windows avoid tests changing calendar bucket mid-assertion.
    limiter.windows=lambda now=None:(100,0,60,86400)
    for _ in range(5): await limiter.check_ip('192.0.2.1')
    with pytest.raises(AppError,match='RATE_LIMITED'): await limiter.check_ip('192.0.2.1')
    keys,_,_=limiter.ip_keys('192.0.2.1')
    assert [int(x) for x in await limiter.redis.mget(keys)]==[5,5]
    assert all('192.0.2.1' not in k for k in keys)
    assert all(0 < ttl <= 172800 for ttl in await asyncio.gather(*(limiter.redis.ttl(k) for k in keys)))
    for minute in range(101,110):
        limiter.windows=lambda now=None,minute=minute:(minute,0,60,86400)
        for _ in range(5): await limiter.check_ip('192.0.2.1')
    limiter.windows=lambda now=None:(110,0,60,86400)
    with pytest.raises(AppError) as exc: await limiter.check_ip('192.0.2.1')
    assert exc.value.code=='RATE_LIMITED' and exc.value.retry_after==86400
    assert int(await limiter.redis.get(keys[1]))==50

@pytest.mark.redis
async def test_real_redis_atomic_ip_and_global_competition(real_limiter):
    limiter=real_limiter
    limiter.windows=lambda now=None:(100,0,60,86400)
    results=await asyncio.gather(*(limiter.check_ip('198.51.100.2') for _ in range(60)),return_exceptions=True)
    assert sum(x is None for x in results)==5
    for _ in range(490): await limiter.reserve_daily()
    results=await asyncio.gather(*(limiter.reserve_daily() for _ in range(60)),return_exceptions=True)
    assert sum(x is None for x in results)==10
    assert all(x.code=='DAILY_QUOTA_EXCEEDED' for x in results if x is not None)
    assert int(await limiter.redis.get(limiter.prefix+':global:0'))==500
    assert 0<await limiter.redis.ttl(limiter.prefix+':global:0')<=172800

async def test_real_disconnected_redis_fails_closed():
    redis=Redis.from_url('redis://127.0.0.1:1/0',socket_connect_timeout=.05,socket_timeout=.05)
    limiter=RateLimiter(redis,SETTINGS.hmac_secret,'test-offline')
    try:
        assert await limiter.ready() is False
        with pytest.raises(AppError,match='LIMITER_UNAVAILABLE'): await limiter.check_ip('test')
        with pytest.raises(AppError,match='LIMITER_UNAVAILABLE'): await limiter.reserve_daily()
    finally: await redis.aclose()

async def test_real_sdk_transport_performs_one_attempt_on_429():
    import httpx
    import openai
    from app.services.ai_client import AIClient
    from app.schemas import ChatRequest
    from .conftest import RESUME
    calls=[]
    async def transport(request):
        calls.append(request)
        return httpx.Response(429,json={'error':{'message':'private upstream detail','type':'rate_limit_error','code':'rate_limit_exceeded'}},request=request)
    ai=AIClient(SETTINGS)
    await ai.sdk.close()
    ai.sdk=openai.AsyncOpenAI(api_key=SETTINGS.api_key,max_retries=0,http_client=httpx.AsyncClient(transport=httpx.MockTransport(transport)),base_url='https://mock.invalid/v1')
    try:
        with pytest.raises(openai.RateLimitError): await ai.complete(RESUME,ChatRequest(question='x'),{})
        assert len(calls)==1
    finally: await ai.close()
