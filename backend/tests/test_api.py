import asyncio
import json
import logging
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from uuid import UUID
import httpx
import openai
import pytest
from app.errors import AppError
from app import main
from .conftest import response, RESUME, FakeLimiter

PATH = '/api/v1/resume/chat'

def assert_error(r, code, status=None):
    data = r.json()
    assert data['error']['code'] == code
    assert UUID(data['request_id'])
    assert r.headers['x-request-id'] == data['request_id']
    assert r.headers['cache-control'] == 'no-store'
    assert set(data) == {'request_id', 'error'}
    if status: assert r.status_code == status
    return data

async def test_normal_history_isolation_and_fixed_prompt(rig):
    async with rig() as h:
        history = [{'role':'user','content':' first visitor '}, {'role':'assistant','content':' fabricated employer '}]
        r = await h.client.post(PATH, json={'question':'  你好  ', 'history':history})
        assert r.status_code == 200 and r.json()['answer']
        assert r.headers['x-request-id'] == r.json()['request_id']
        first = h.ai.sdk.responses.create.call_args.kwargs
        assert first['model'] == 'test-model' and first['store'] is False and first['max_output_tokens'] == 1500
        assert first['reasoning'] == {'effort': 'none'}
        assert 'temperature' not in first and 'tools' not in first and 'background' not in first
        assert '事实，只能来自' in first['instructions']
        data = json.loads(first['input'][1]['content'])
        assert json.loads(first['input'][0]['content'])['public_resume'] == RESUME and data['current_question'] == '你好'
        assert data['untrusted_history'][0]['content'] == 'first visitor'
        second = await h.client.post(PATH, json={'question':'other visitor'})
        assert second.json()['request_id'] != r.json()['request_id']
        assert json.loads(h.ai.sdk.responses.create.call_args.kwargs['input'][1]['content'])['untrusted_history'] == []
        assert h.ai.sdk.max_retries == 0

@pytest.mark.parametrize('body', [{}, {'question':None}, {'question':32}, {'question':[]}, {'question':' \t\n '}, {'question':'x','model':'evil'}, {'question':'x','history':None}, {'question':'x','history':[{'role':'user','content':'x','extra':1},{'role':'assistant','content':'x'}]}])
async def test_invalid_fields(rig, body):
    async with rig() as h:
        assert_error(await h.client.post(PATH,json=body),'VALIDATION_ERROR',422)
        h.ai.sdk.responses.create.assert_not_called()
        assert h.limiter.ip_calls == 0

@pytest.mark.parametrize('text,valid', [('好',True),('😀'*1000,True),('😀'*1001,False),('你好\n\t世界',True),('你\x00好',False),('你\r好',False),('\ud800',False)])
async def test_question_unicode_boundaries(rig,text,valid):
    async with rig() as h:
        r=await h.client.post(PATH,content=json.dumps({'question':text}),headers={'Content-Type':'application/json; charset=utf-8'})
        assert r.status_code == (200 if valid else 422)

def histories(lengths):
    return [{'role': 'user' if i%2==0 else 'assistant','content':'字'*n} for i,n in enumerate(lengths)]

@pytest.mark.parametrize('history,valid', [([],True),(histories([1,1]),True),(histories([1]*4),True),(histories([1000,1000]*3),True),(histories([1000,1001]*3),False),(histories([1]*8),False),(histories([1]),False),(histories([1001,1]),False),(histories([1,2001]),False),([{'role':'system','content':'a'},{'role':'assistant','content':'b'}],False),([{'role':'assistant','content':'a'},{'role':'user','content':'b'}],False),([{'role':'user','content':1},{'role':'assistant','content':'b'}],False),([{'role':'user','content':' '},{'role':'assistant','content':'b'}],False)])
async def test_history_limits(rig,history,valid):
    async with rig() as h:
        r=await h.client.post(PATH,json={'question':'x','history':history})
        assert r.status_code == (200 if valid else 422)

@pytest.mark.parametrize('size,stream', [(49152,False),(49153,False),(49152,True),(49153,True)])
async def test_body_exact_limit_and_chunked(rig,size,stream):
    body=b'{"question":"x"}'+b' '*(size-16)
    assert len(body)==size
    async def chunks():
        for i in range(0,len(body),1000): yield body[i:i+1000]
    async with rig() as h:
        r=await h.client.post(PATH,content=chunks() if stream else body,headers={'Content-Type':'application/json'})
        assert r.status_code == (200 if size==49152 else 413)
        if size>49152: h.ai.sdk.responses.create.assert_not_called()

@pytest.mark.parametrize('body', [b'{',b'\xff',b'{"question":"x","question":"y"}',b'{"question":NaN}',b'\xef\xbb\xbf{"question":"x"}'])
async def test_invalid_json(rig,body):
    async with rig() as h: assert_error(await h.client.post(PATH,content=body,headers={'Content-Type':'application/json'}),'INVALID_JSON',400)

@pytest.mark.parametrize('headers',[{}, {'Content-Type':'text/plain'},{'Content-Type':'application/json','Content-Encoding':'gzip'}])
async def test_media_type(rig,headers):
    async with rig() as h: assert_error(await h.client.post(PATH,content=b'{}',headers=headers),'UNSUPPORTED_MEDIA_TYPE',415)

async def test_resume_not_ready_health_and_routes(rig):
    async with rig(resume=None) as h:
        assert_error(await h.client.post(PATH,json={'question':'x'}),'RESUME_UNAVAILABLE',503)
        assert (await h.client.get('/health/live')).json()=={'status':'ok'}
        assert (await h.client.get('/health/ready')).status_code==503
        assert h.limiter.ip_calls==0
        h.ai.sdk.responses.create.assert_not_called()
        assert_error(await h.client.get('/missing'),'NOT_FOUND',404)
        assert_error(await h.client.get(PATH),'METHOD_NOT_ALLOWED',405)

async def test_limiter_and_pool_order(rig):
    async with rig() as h:
        h.app.state.pool.active=4
        assert_error(await h.client.post(PATH,json={'question':'x'}),'AI_UNAVAILABLE',503)
        assert h.limiter.ip_calls==1 and h.limiter.daily_calls==0
        h.ai.sdk.responses.create.assert_not_called()
        h.app.state.pool.active=0
        h.limiter.reserve_daily=AsyncMock(side_effect=AppError('DAILY_QUOTA_EXCEEDED',60))
        r=await h.client.post(PATH,json={'question':'x'})
        assert_error(r,'DAILY_QUOTA_EXCEEDED',503)
        assert r.headers['retry-after']=='60' and h.app.state.pool.active==0

async def test_redis_failure_before_model(rig):
    limiter=FakeLimiter();limiter.check_ip=AsyncMock(side_effect=AppError('LIMITER_UNAVAILABLE'))
    async with rig(limiter=limiter) as h:
        assert_error(await h.client.post(PATH,json={'question':'x'}),'LIMITER_UNAVAILABLE',503)
        h.ai.sdk.responses.create.assert_not_called()

@pytest.mark.parametrize('status,code',[(429,'AI_UNAVAILABLE'),(500,'AI_UNAVAILABLE'),(401,'AI_CONFIGURATION_ERROR'),(404,'AI_CONFIGURATION_ERROR'),(400,'AI_CONFIGURATION_ERROR')])
async def test_upstream_http_mapping_without_retry(rig,status,code):
    async with rig() as h:
        h.ai.sdk.responses.create.side_effect=openai.APIStatusError('SENSITIVE upstream exception',response=httpx.Response(status,request=httpx.Request('POST','https://api.deepseek.com/responses')),body=None)
        assert_error(await h.client.post(PATH,json={'question':'x'}),code,503)
        assert h.ai.sdk.responses.create.call_count==1 and h.app.state.pool.active==0

@pytest.mark.parametrize('upstream',[response(''),response('x'*2001),response(status='incomplete'),NS(status='completed',output=[],usage=None),NS(status='completed',output=[NS(type='function_call')],usage=None)])
async def test_invalid_upstream(rig,upstream):
    async with rig(sdk_response=upstream) as h:
        assert_error(await h.client.post(PATH,json={'question':'x'}),'AI_INVALID_RESPONSE',502)
        assert h.ai.sdk.responses.create.call_count==1

async def test_timeout_and_cancel_release(rig,monkeypatch):
    async def hang(**kwargs): await asyncio.Event().wait()
    monkeypatch.setattr(main,'MODEL_TIMEOUT',0.03)
    async with rig() as h:
        h.ai.sdk.responses.create.side_effect=hang
        assert_error(await h.client.post(PATH,json={'question':'x'}),'AI_TIMEOUT',504)
        assert h.app.state.pool.active==0
        monkeypatch.setattr(main,'MODEL_TIMEOUT',30)
        task=asyncio.create_task(h.client.post(PATH,json={'question':'x'}))
        while h.app.state.pool.active==0: await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        assert h.app.state.pool.active==0

async def test_total_deadline_covers_body_and_redis(rig,monkeypatch):
    monkeypatch.setattr(main,'TOTAL_TIMEOUT',0.03)
    async def slow_body():
        yield b'{'
        await asyncio.sleep(1)
        yield b'}'
    async with rig() as h:
        assert_error(await h.client.post(PATH,content=slow_body(),headers={'Content-Type':'application/json'}),'AI_TIMEOUT',504)
        async def hang(ip): await asyncio.Event().wait()
        h.limiter.check_ip=hang
        assert_error(await h.client.post(PATH,json={'question':'x'}),'AI_TIMEOUT',504)
        h.ai.sdk.responses.create.assert_not_called()
        assert h.app.state.pool.active==0

async def test_safe_logs_and_unexpected_error(rig,caplog):
    caplog.set_level(logging.INFO,logger='resume.runtime')
    async with rig(resume='SECRET_RESUME'*20) as h:
        h.ai.sdk.responses.create.return_value=response('SECRET_ANSWER')
        await h.client.post(PATH,json={'question':'SECRET_QUESTION'})
        h.ai.sdk.responses.create.side_effect=RuntimeError('SECRET_EXCEPTION')
        assert_error(await h.client.post(PATH,json={'question':'SECRET_QUESTION'}),'INTERNAL_ERROR',500)
    assert all(s not in caplog.text for s in ['SECRET_RESUME','SECRET_ANSWER','SECRET_QUESTION','SECRET_EXCEPTION','127.0.0.1','test-secret-key'])
    assert 'request_id' in caplog.text and 'model_ms' in caplog.text

async def test_cors_preflight_and_headers(rig):
    async with rig() as h:
        r=await h.client.options(PATH,headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'Content-Type'})
        assert r.status_code==200 and r.headers['access-control-allow-origin']=='http://localhost:5173'
        assert UUID(r.headers['x-request-id']) and r.headers['cache-control']=='no-store'
        r=await h.client.options(PATH,headers={'Origin':'https://evil.example','Access-Control-Request-Method':'POST'})
        assert_error(r,'CORS_REJECTED',400)

async def test_four_real_concurrent_tasks_reject_fifth_and_release(rig):
    async with rig() as h:
        async def hang(**kwargs): await asyncio.Event().wait()
        h.ai.sdk.responses.create.side_effect=hang
        tasks=[asyncio.create_task(h.client.post(PATH,json={'question':'x'})) for _ in range(4)]
        try:
            async with asyncio.timeout(1):
                while h.ai.sdk.responses.create.call_count<4: await asyncio.sleep(0)
            r=await h.client.post(PATH,json={'question':'fifth'})
            assert_error(r,'AI_UNAVAILABLE',503)
            assert h.ai.sdk.responses.create.call_count==4 and h.limiter.daily_calls==4
        finally:
            for t in tasks: t.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
        assert h.app.state.pool.active==0

async def test_boundary_timeout_remains_readable_cross_origin(rig,monkeypatch):
    monkeypatch.setattr(main,'TOTAL_TIMEOUT',.02)
    async def slow():
        yield b'{' ; await asyncio.sleep(1)
    async with rig() as h:
        r=await h.client.post(PATH,content=slow(),headers={'Content-Type':'application/json','Origin':'http://localhost:5173'})
        assert_error(r,'AI_TIMEOUT',504)
        assert r.headers['access-control-allow-origin']=='http://localhost:5173'
