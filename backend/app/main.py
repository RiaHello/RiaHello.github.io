import asyncio
from contextlib import asynccontextmanager, aclosing
import json
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import ClientDisconnect
from starlette.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError
from redis.asyncio import Redis

from app.config import Settings
from app.errors import AppError
from app.schemas import ChatRequest
from app.services.ai_client import AIClient, map_ai_error
from app.services.rate_limiter import RateLimiter
from app.services.resume_loader import load_resume

logger = logging.getLogger('resume.runtime')
TOTAL_TIMEOUT = 35.0
MODEL_TIMEOUT = 30.0
BODY_LIMIT = 49152
_UNSET = object()


def error_response(error, state):
    state['error_code'] = error.code
    headers = {'Retry-After': str(error.retry_after)} if error.retry_after is not None else {}
    if state.get('cors_origin'):
        headers.update({'Access-Control-Allow-Origin': state['cors_origin'], 'Vary': 'Origin', 'Access-Control-Expose-Headers': 'X-Request-ID, Retry-After'})
    return JSONResponse(error.body(state['request_id']), status_code=error.status, headers=headers)


def event(name, payload):
    return f'event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n'.encode()


class RequestBoundary:
    """Pure ASGI boundary: deadline includes receiving the body and sending a stream."""
    def __init__(self, app): self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        start = time.monotonic()
        state = scope.setdefault('state', {})
        state.update(request_id=str(uuid4()), deadline=start + TOTAL_TIMEOUT)
        started = False
        status = 500
        streaming = False
        finished = False
        async def wrapped_send(message):
            nonlocal started, status, streaming, finished
            if message['type'] == 'http.response.start':
                started, status = True, message['status']
                headers = [(k, v) for k, v in message.get('headers', []) if k.lower() not in (b'x-request-id', b'cache-control')]
                streaming = any(k.lower() == b'content-type' and b'text/event-stream' in v for k, v in headers)
                headers += [(b'x-request-id', state['request_id'].encode()), (b'cache-control', b'no-store')]
                message = {**message, 'headers': headers}
            await send(message)
            if message['type'] == 'http.response.body' and not message.get('more_body', False):
                finished = True
        try:
            async with asyncio.timeout_at(state['deadline']):
                await self.app(scope, receive, wrapped_send)
        except ClientDisconnect:
            state['error_code'] = 'CLIENT_DISCONNECTED'
        except asyncio.CancelledError:
            state['error_code'] = 'CLIENT_DISCONNECTED'
            raise
        except Exception as exc:
            err = AppError('AI_TIMEOUT' if isinstance(exc, TimeoutError) else 'INTERNAL_ERROR')
            state['error_code'] = err.code
            if not started:
                await error_response(err, state)(scope, receive, wrapped_send)
            elif streaming and not finished:
                await send({'type': 'http.response.body', 'body': event('error', err.body(state['request_id'])), 'more_body': False})
        finally:
            # Never interpolate exceptions, arbitrary route paths, headers, addresses or user data.
            route = scope.get('route')
            logger.info(json.dumps({'request_id': state['request_id'], 'route': getattr(route, 'path', 'unmatched'),
                'status': status, 'error_code': state.get('error_code'), 'elapsed_ms': round((time.monotonic()-start)*1000),
                'model_ms': state.get('model_ms'), 'model': state.get('model'), 'tokens': state.get('tokens')}))


class Pool:
    def __init__(self): self.active = 0
    def acquire(self):
        if self.active >= 4: raise AppError('AI_UNAVAILABLE')
        self.active += 1
        return Lease(self)

class Lease:
    def __init__(self, pool): self.pool, self.released = pool, False
    def release(self):
        if not self.released:
            self.released = True
            self.pool.active -= 1

class LeasedStream(StreamingResponse):
    def __init__(self, content, lease):
        super().__init__(content, media_type='text/event-stream', headers={'X-Accel-Buffering': 'no'})
        self.lease = lease
    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            # Close suspended generators immediately on ASGI send failures, too.
            try:
                close = getattr(self.body_iterator, 'aclose', None)
                if close is not None: await close()
            finally:
                self.lease.release()


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('duplicate')
        result[key] = value
    return result

def reject_constant(_): raise ValueError('non-finite')

async def parse_body(request):
    if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json' or request.headers.get('content-encoding', 'identity').lower() not in ('', 'identity'):
        raise AppError('UNSUPPORTED_MEDIA_TYPE')
    size = 0
    chunks = []
    async for chunk in request.stream():
        size += len(chunk)
        if size > BODY_LIMIT: raise AppError('PAYLOAD_TOO_LARGE')
        chunks.append(chunk)
    try:
        data = json.loads(b''.join(chunks).decode('utf-8'), object_pairs_hook=strict_object, parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise AppError('INVALID_JSON') from None
    try:
        return ChatRequest.model_validate(data)
    except ValidationError:
        raise AppError('VALIDATION_ERROR') from None

async def run_with_disconnect(request, operation):
    async def disconnected():
        while True:
            if (await request.receive())['type'] == 'http.disconnect': return
    work = asyncio.create_task(operation)
    watch = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait((work, watch), return_when=asyncio.FIRST_COMPLETED)
        if watch in done: raise ClientDisconnect()
        return await work
    finally:
        work.cancel()
        watch.cancel()
        await asyncio.gather(work, watch, return_exceptions=True)


def create_app(*, settings=None, limiter=None, ai=None, resume=_UNSET):
    """Python-only dependency injection for isolated tests; never HTTP/configurable file paths."""
    owned = {}
    @asynccontextmanager
    async def lifespan(app):
        config = settings or Settings.from_env()
        app.state.settings = config
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            logger.addHandler(handler)
        app.state.resume = load_resume() if resume is _UNSET else resume
        app.state.pool = Pool()
        if limiter is None:
            redis = Redis.from_url(config.redis_url, socket_timeout=2, socket_connect_timeout=2, retry_on_timeout=False)
            app.state.limiter = RateLimiter(redis, config.hmac_secret)
            owned['redis'] = redis
        else: app.state.limiter = limiter
        app.state.ai = ai or AIClient(config)
        for name in ('openai', 'httpx', 'httpcore'):
            logging.getLogger(name).setLevel(logging.CRITICAL)
        # CORS needs validated environment settings, available only once startup has run.
        app.state.cors_origins = config.origins
        try:
            yield
        finally:
            if ai is None: await app.state.ai.close()
            if 'redis' in owned: await owned['redis'].aclose()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None, debug=False)
    app.add_middleware(RequestBoundary)

    @app.exception_handler(AppError)
    async def app_error(request, exc): return error_response(exc, request.scope['state'])
    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc): return error_response(AppError('VALIDATION_ERROR'), request.scope['state'])
    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error_response(AppError('NOT_FOUND' if exc.status_code == 404 else 'METHOD_NOT_ALLOWED' if exc.status_code == 405 else 'INTERNAL_ERROR'), request.scope['state'])

    @app.get('/health/live')
    async def live(): return {'status': 'ok'}

    @app.get('/health/ready')
    async def ready():
        ready = app.state.resume is not None and await app.state.limiter.ready()
        return JSONResponse({'status': 'ready' if ready else 'not_ready'}, status_code=200 if ready else 503)

    @app.post('/api/v1/resume/chat')
    async def chat(request: Request):
        body = await parse_body(request)
        if app.state.resume is None: raise AppError('RESUME_UNAVAILABLE')
        await app.state.limiter.check_ip(request.client.host if request.client else 'unknown')
        lease = app.state.pool.acquire()
        try:
            await app.state.limiter.reserve_daily()
        except BaseException:
            lease.release()
            raise
        state = request.scope['state']
        state['model'] = app.state.settings.model
        if 'text/event-stream' in request.headers.get('accept', '').lower():
            async def generate():
                started = time.monotonic()
                try:
                    async with asyncio.timeout(min(MODEL_TIMEOUT, max(0, state['deadline'] - time.monotonic()))):
                        async with aclosing(app.state.ai.stream(app.state.resume, body, state)) as upstream:
                            async for kind, text in upstream:
                                yield event(kind, {'request_id': state['request_id'], 'answer' if kind == 'done' else 'delta': text})
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    err = map_ai_error(exc)
                    state['error_code'] = err.code
                    yield event('error', err.body(state['request_id']))
                finally:
                    state['model_ms'] = round((time.monotonic()-started)*1000)
                    lease.release()
            return LeasedStream(generate(), lease)
        started = time.monotonic()
        try:
            async with asyncio.timeout(min(MODEL_TIMEOUT, max(0, state['deadline'] - time.monotonic()))):
                answer = await run_with_disconnect(request, app.state.ai.complete(app.state.resume, body, state))
            return {'request_id': state['request_id'], 'answer': answer}
        except (asyncio.CancelledError, ClientDisconnect):
            raise
        except Exception as exc:
            raise map_ai_error(exc) from None
        finally:
            state['model_ms'] = round((time.monotonic()-started)*1000)
            lease.release()

    # Dynamic CORS wrapper is inside the request boundary so preflights also receive
    # IDs, no-store, the deadline, and the same sanitized errors.
    class DynamicCORS:
        def __init__(self, app): self.inner = app
        async def __call__(self, scope, receive, send):
            if scope['type'] == 'http':
                origin = next((v.decode('latin-1') for k, v in scope['headers'] if k == b'origin'), None)
                if origin in getattr(app.state, 'cors_origins', ()):
                    scope.setdefault('state', {})['cors_origin'] = origin
            cors = CORSMiddleware(self.inner, allow_origins=list(getattr(app.state, 'cors_origins', ())),
                allow_methods=['GET', 'POST'], allow_headers=['Content-Type', 'Accept'],
                expose_headers=['X-Request-ID', 'Retry-After'], allow_credentials=False)
            if scope['type'] == 'http' and scope['method'] == 'OPTIONS' and any(k == b'access-control-request-method' for k, _ in scope['headers']):
                from starlette.datastructures import Headers
                response = cors.preflight_response(Headers(scope=scope))
                if response.status_code != 200:
                    response = error_response(AppError('CORS_REJECTED'), scope['state'])
                await response(scope, receive, send)
            else:
                await cors(scope, receive, send)
    app.add_middleware(DynamicCORS)
    # Starlette inserts new middleware first; boundary must remain outermost user middleware.
    app.user_middleware.reverse()
    return app

app = create_app()
