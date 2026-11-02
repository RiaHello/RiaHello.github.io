import asyncio
from types import SimpleNamespace as NS
import pytest
from app import main
from .conftest import response
from .test_api import PATH, assert_error

class FakeStream:
    def __init__(self,events,hang=False): self.events,self.closed,self.hang=events,False,hang
    async def __aenter__(self): return self
    async def __aexit__(self,*args): self.closed=True
    async def __aiter__(self):
        for e in self.events: yield e
        if self.hang: await asyncio.Event().wait()

def delta(text): return NS(type='response.output_text.delta',delta=text)
def done(text): return NS(type='response.completed',response=response(text))

async def test_sse_done_and_invalid_partial(rig):
    async with rig() as h:
        stream=FakeStream([delta('你好'),done('你好')])
        h.ai.sdk.responses.create.return_value=stream
        r=await h.client.post(PATH,json={'question':'x'},headers={'Accept':'text/event-stream'})
        assert r.status_code==200 and 'event: delta' in r.text and 'event: done' in r.text
        assert '"answer": "你好"' in r.text and stream.closed and h.app.state.pool.active==0
        assert h.ai.sdk.responses.create.call_args.kwargs['stream'] is True
        stream=FakeStream([delta('半句话'),NS(type='response.incomplete')])
        h.ai.sdk.responses.create.return_value=stream
        r=await h.client.post(PATH,json={'question':'x'},headers={'Accept':'text/event-stream'})
        assert 'event: error' in r.text and 'AI_INVALID_RESPONSE' in r.text and 'event: done' not in r.text
        assert stream.closed and h.app.state.pool.active==0

async def test_sse_timeout_and_preflight_error(rig,monkeypatch):
    monkeypatch.setattr(main,'MODEL_TIMEOUT',.03)
    async with rig() as h:
        stream=FakeStream([delta('临时文本')],hang=True)
        h.ai.sdk.responses.create.return_value=stream
        r=await h.client.post(PATH,json={'question':'x'},headers={'Accept':'text/event-stream'})
        assert 'event: error' in r.text and 'AI_TIMEOUT' in r.text and stream.closed
        assert h.app.state.pool.active==0
        r=await h.client.post(PATH,json={'question':None},headers={'Accept':'text/event-stream'})
        assert_error(r,'VALIDATION_ERROR',422)

async def test_actual_asgi_disconnect_releases_json_and_stream(rig):
    for streaming in (False,True):
        async with rig() as h:
            entered=asyncio.Event()
            cancelled=asyncio.Event()
            async def hanging(*args,**kwargs):
                entered.set()
                try: await asyncio.Event().wait()
                finally: cancelled.set()
            async def hanging_stream(*args,**kwargs):
                entered.set()
                try:
                    yield 'delta','临时'
                    await asyncio.Event().wait()
                finally: cancelled.set()
            h.ai.complete=hanging
            h.ai.stream=hanging_stream
            messages=asyncio.Queue()
            await messages.put({'type':'http.request','body':b'{"question":"x"}','more_body':False})
            headers=[(b'content-type',b'application/json')]
            if streaming: headers.append((b'accept',b'text/event-stream'))
            scope={'type':'http','asgi':{'version':'3.0','spec_version':'2.3'},'http_version':'1.1','method':'POST','scheme':'http','path':PATH,'raw_path':PATH.encode(),'query_string':b'','headers':headers,'client':('192.0.2.3',1234),'server':('test',80)}
            sent=[]
            async def send(message): sent.append(message)
            task=asyncio.create_task(h.app(scope,messages.get,send))
            await asyncio.wait_for(entered.wait(),1)
            await messages.put({'type':'http.disconnect'})
            await asyncio.wait_for(task,1)
            assert cancelled.is_set() and h.app.state.pool.active==0

@pytest.mark.parametrize('code,expected',[('server_error','AI_UNAVAILABLE'),('rate_limit_exceeded','AI_UNAVAILABLE'),('invalid_api_key','AI_CONFIGURATION_ERROR'),('model_not_found','AI_CONFIGURATION_ERROR'),('invalid_request_error','AI_CONFIGURATION_ERROR'),('unknown','AI_INVALID_RESPONSE')])
@pytest.mark.parametrize('kind',['error','response.failed'])
async def test_sse_provider_error_mapping(rig,code,expected,kind):
    async with rig() as h:
        failed=NS(type=kind,code=code,response=NS(error=NS(code=code,message='PRIVATE_ERROR')),message='PRIVATE_ERROR')
        stream=FakeStream([failed]);h.ai.sdk.responses.create.return_value=stream
        r=await h.client.post(PATH,json={'question':'x'},headers={'Accept':'text/event-stream'})
        assert expected in r.text and 'PRIVATE_ERROR' not in r.text and stream.closed
        assert h.app.state.pool.active==0

async def test_asgi_24_send_disconnect_closes_upstream_immediately(rig):
    async with rig() as h:
        stream=FakeStream([delta('临时'),done('临时')]);h.ai.sdk.responses.create.return_value=stream
        messages=asyncio.Queue()
        await messages.put({'type':'http.request','body':b'{"question":"x"}','more_body':False})
        scope={'type':'http','asgi':{'version':'3.0','spec_version':'2.4'},'http_version':'1.1','method':'POST','scheme':'http','path':PATH,'raw_path':PATH.encode(),'query_string':b'','headers':[(b'content-type',b'application/json'),(b'accept',b'text/event-stream')],'client':('192.0.2.3',1234),'server':('test',80)}
        async def send(message):
            if message['type']=='http.response.body': raise OSError('connection closed')
        await h.app(scope,messages.get,send)
        assert stream.closed and h.app.state.pool.active==0

async def test_total_stream_deadline(rig,monkeypatch):
    monkeypatch.setattr(main,'TOTAL_TIMEOUT',.03)
    async with rig() as h:
        stream=FakeStream([delta('临时')],hang=True);h.ai.sdk.responses.create.return_value=stream
        r=await h.client.post(PATH,json={'question':'x'},headers={'Accept':'text/event-stream'})
        assert 'AI_TIMEOUT' in r.text and 'event: done' not in r.text
        assert stream.closed and h.app.state.pool.active==0
