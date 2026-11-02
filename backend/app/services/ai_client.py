import json
from pathlib import Path
import httpx
from openai import AsyncOpenAI, APIConnectionError, APIStatusError, APITimeoutError
from app.errors import AppError

PROMPT = (Path(__file__).resolve().parents[1] / 'prompts' / 'resume_assistant.txt').read_text(encoding='utf-8')

def provider_error(code):
    if code in ('server_error', 'rate_limit_exceeded', 'service_unavailable', 'overloaded'):
        return AppError('AI_UNAVAILABLE')
    if code in ('invalid_api_key', 'model_not_found', 'invalid_request', 'invalid_request_error', 'invalid_prompt', 'data_residency_mismatch', 'unsupported_parameter', 'permission_denied'):
        return AppError('AI_CONFIGURATION_ERROR')
    return AppError('AI_INVALID_RESPONSE')

def validate_response(response):
    if response.status == 'failed':
        raise provider_error(getattr(getattr(response, 'error', None), 'code', None))
    if response.status != 'completed' or not response.output:
        raise AppError('AI_INVALID_RESPONSE')
    texts = []
    for item in response.output:
        # Reasoning metadata is permitted; tools and other non-text outputs are not.
        if item.type == 'reasoning': continue
        if item.type != 'message' or item.status != 'completed': raise AppError('AI_INVALID_RESPONSE')
        for content in item.content:
            if content.type != 'output_text': raise AppError('AI_INVALID_RESPONSE')
            texts.append(content.text)
    answer = ''.join(texts).strip()
    if not 1 <= len(answer) <= 2000: raise AppError('AI_INVALID_RESPONSE')
    return answer

def map_ai_error(exc):
    if isinstance(exc, AppError): return exc
    if isinstance(exc, (TimeoutError, APITimeoutError)): return AppError('AI_TIMEOUT')
    if isinstance(exc, APIConnectionError): return AppError('AI_UNAVAILABLE')
    if isinstance(exc, APIStatusError):
        if exc.status_code in (400, 401, 402, 403, 404, 422): return AppError('AI_CONFIGURATION_ERROR')
        if exc.status_code == 429 or exc.status_code >= 500: return AppError('AI_UNAVAILABLE')
    return AppError('INTERNAL_ERROR')

class AIClient:
    def __init__(self, settings):
        self.model = settings.model
        self.sdk = AsyncOpenAI(api_key=settings.api_key, base_url='https://api.deepseek.com', max_retries=0,
            timeout=httpx.Timeout(30, connect=5), http_client=httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5), trust_env=False))

    def arguments(self, resume, body):
        # All visitor text is serialized as untrusted data, never instructions or assistant authority.
        data = {'untrusted_history': [m.model_dump() for m in body.history], 'current_question': body.question}
        return dict(model=self.model, instructions=PROMPT, input=[{'role': 'user', 'content': json.dumps({'public_resume': resume}, ensure_ascii=False)}, {'role': 'user', 'content': json.dumps(data, ensure_ascii=False)}],
                    store=False, max_output_tokens=1500, reasoning={'effort': 'none'})

    async def complete(self, resume, body, state):
        response = await self.sdk.responses.create(**self.arguments(resume, body))
        self.record_usage(response, state)
        return validate_response(response)

    async def stream(self, resume, body, state):
        stream = await self.sdk.responses.create(**self.arguments(resume, body), stream=True)
        complete = False
        partial = ''
        async with stream:
            async for event in stream:
                if event.type == 'response.output_text.delta':
                    partial += event.delta
                    if len(partial) > 2000: raise AppError('AI_INVALID_RESPONSE')
                    yield 'delta', event.delta
                elif event.type == 'response.completed':
                    self.record_usage(event.response, state)
                    answer = validate_response(event.response)
                    complete = True
                    yield 'done', answer
                    break
                elif event.type == 'response.failed':
                    raise provider_error(getattr(getattr(event.response, 'error', None), 'code', None))
                elif event.type == 'error':
                    raise provider_error(event.code)
                elif event.type == 'response.incomplete':
                    raise AppError('AI_INVALID_RESPONSE')
        if not complete: raise AppError('AI_INVALID_RESPONSE')

    @staticmethod
    def record_usage(response, state):
        usage = getattr(response, 'usage', None)
        if usage:
            state['tokens'] = {key: getattr(usage, key, None) for key in ('input_tokens', 'output_tokens', 'total_tokens')}

    async def close(self):
        await self.sdk.close()
