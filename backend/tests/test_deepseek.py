"""Exercise the installed SDK against MockTransport, never the real provider."""
from contextlib import asynccontextmanager
import json

import httpx
import pytest

from app.config import ConfigurationError, Settings
from app.errors import AppError
from app.schemas import ChatRequest
from app.services.ai_client import AIClient, map_ai_error
from .conftest import RESUME

SETTINGS = Settings('offline-deepseek-test-key', 'deepseek-flash', 'offline-test-hmac-secret-' * 3)


def response_payload(status='completed'):
    return {
        'id': 'resp_offline', 'object': 'response', 'created_at': 1,
        'model': 'deepseek-flash', 'status': status, 'store': False,
        'output': [{'id': 'msg_offline', 'type': 'message', 'status': 'completed',
                    'role': 'assistant', 'content': [{'type': 'output_text', 'text': '根据公开简历，参与过示例项目。', 'annotations': []}]}],
        'usage': {'input_tokens': 10, 'output_tokens': 12, 'total_tokens': 22},
    }


@asynccontextmanager
async def sdk_transport(handler):
    ai = AIClient(SETTINGS)
    original = ai.sdk
    # with_options preserves the production constructor's base URL and retry policy.
    ai.sdk = original.with_options(http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False))
    await original.close()
    try:
        yield ai
    finally:
        await ai.close()


def assert_request(request, *, streaming=False):
    assert str(request.url) == 'https://api.deepseek.com/responses'
    assert request.method == 'POST'
    assert request.headers['authorization'] == 'Bearer offline-deepseek-test-key'
    body = json.loads(request.content)
    assert body['model'] == 'deepseek-flash'
    assert body['reasoning'] == {'effort': 'none'}
    assert body['max_output_tokens'] == 1500 and body['store'] is False
    assert body.get('stream', False) is streaming
    assert 'temperature' not in body and 'tools' not in body and 'background' not in body
    assert '事实，只能来自' in body['instructions']
    assert json.loads(body['input'][0]['content'])['public_resume'] == RESUME
    assert json.loads(body['input'][1]['content'])['current_question'] == '项目经历？'


async def test_deepseek_sdk_json_transport_and_fixed_endpoint(monkeypatch):
    # Generic SDK environment variables cannot redirect the fixed service endpoint.
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://untrusted.invalid')
    calls = []
    async def handler(request):
        calls.append(request)
        assert_request(request)
        return httpx.Response(200, json=response_payload())
    async with sdk_transport(handler) as ai:
        state = {}
        assert await ai.complete(RESUME, ChatRequest(question='项目经历？'), state) == '根据公开简历，参与过示例项目。'
        assert state['tokens'] == {'input_tokens': 10, 'output_tokens': 12, 'total_tokens': 22}
        assert ai.sdk.max_retries == 0 and len(calls) == 1


def sse(events):
    return ''.join(f'event: {item["type"]}\ndata: {json.dumps(item, ensure_ascii=False)}\n\n' for item in events).encode()


async def test_deepseek_sdk_semantic_sse_parse():
    calls = []
    events = [
        {'type': 'response.output_text.delta', 'delta': '根据公开简历，', 'sequence_number': 1, 'content_index': 0, 'output_index': 0, 'item_id': 'msg_offline', 'logprobs': []},
        {'type': 'response.completed', 'response': response_payload(), 'sequence_number': 2},
    ]
    async def handler(request):
        calls.append(request)
        assert_request(request, streaming=True)
        return httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, content=sse(events))
    async with sdk_transport(handler) as ai:
        state = {}
        results = [item async for item in ai.stream(RESUME, ChatRequest(question='项目经历？'), state)]
        assert results == [('delta', '根据公开简历，'), ('done', '根据公开简历，参与过示例项目。')]
        assert state['tokens']['total_tokens'] == 22 and len(calls) == 1


@pytest.mark.parametrize('status,expected', [(401, 'AI_CONFIGURATION_ERROR'), (402, 'AI_CONFIGURATION_ERROR'), (429, 'AI_UNAVAILABLE'), (503, 'AI_UNAVAILABLE')])
@pytest.mark.parametrize('streaming', [False, True])
async def test_deepseek_sdk_http_errors_and_no_retry(status, expected, streaming):
    calls = []
    async def handler(request):
        calls.append(request)
        assert_request(request, streaming=streaming)
        return httpx.Response(status, json={'error': {'message': 'PRIVATE_PROVIDER_DETAIL', 'type': 'api_error', 'code': 'provider_error'}})
    async with sdk_transport(handler) as ai:
        with pytest.raises(Exception) as exc:
            if streaming:
                _ = [item async for item in ai.stream(RESUME, ChatRequest(question='项目经历？'), {})]
            else:
                await ai.complete(RESUME, ChatRequest(question='项目经历？'), {})
        mapped = map_ai_error(exc.value)
        assert mapped.code == expected and len(calls) == 1
        assert mapped.body('test-request')['error']['retryable'] is (expected == 'AI_UNAVAILABLE')
        assert 'PRIVATE_PROVIDER_DETAIL' not in json.dumps(mapped.body('test-request'))


@pytest.mark.parametrize('event_type,expected', [('response.incomplete', 'AI_INVALID_RESPONSE'), ('response.failed', 'AI_UNAVAILABLE')])
async def test_deepseek_sdk_unsuccessful_sse_terminal(event_type, expected):
    payload = response_payload('incomplete' if event_type == 'response.incomplete' else 'failed')
    if event_type == 'response.failed': payload['error'] = {'code': 'server_error', 'message': 'PRIVATE_PROVIDER_DETAIL'}
    async def handler(request):
        assert_request(request, streaming=True)
        return httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, content=sse([{'type': event_type, 'response': payload, 'sequence_number': 1}]))
    async with sdk_transport(handler) as ai:
        with pytest.raises(AppError) as exc:
            _ = [item async for item in ai.stream(RESUME, ChatRequest(question='项目经历？'), {})]
        assert exc.value.code == expected


def test_deepseek_credentials_required_without_legacy_fallback(monkeypatch):
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.delenv('DEEPSEEK_MODEL', raising=False)
    monkeypatch.setenv('OPENAI_API_KEY', 'legacy-secret-must-not-be-used')
    monkeypatch.setenv('OPENAI_MODEL', 'legacy-model-must-not-be-used')
    monkeypatch.setenv('RATE_LIMIT_HMAC_SECRET', 'offline-test-secret-' * 3)
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('ALLOWED_ORIGINS', 'http://localhost:5173')
    with pytest.raises(ConfigurationError) as exc:
        Settings.from_env()
    assert str(exc.value) == 'DEEPSEEK_API_KEY,DEEPSEEK_MODEL'
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'offline-deepseek-test-key')
    monkeypatch.setenv('DEEPSEEK_MODEL', 'deepseek-flash')
    config = Settings.from_env()
    assert config.api_key == 'offline-deepseek-test-key' and config.model == 'deepseek-flash'
