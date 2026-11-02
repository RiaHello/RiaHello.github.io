import test from 'node:test';
import assert from 'node:assert/strict';
import { buildHistory, codePointLength, normalizeQuestion, requestResumeAnswer } from '../src/lib/resume-chat.js';

const responseId = 'd637b078-22c2-4c16-8736-96cb9e0e75f2';
const event = (type, data) => `event: ${type}\r\ndata: ${JSON.stringify({ request_id: responseId, ...data })}\r\n\r\n`;
const streamingFetch = (text, chunkSize = 7) => async () => {
  const bytes = new TextEncoder().encode(text);
  return new Response(new ReadableStream({
    start(controller) {
      for (let i = 0; i < bytes.length; i += chunkSize) controller.enqueue(bytes.slice(i, i + chunkSize));
      controller.close();
    },
  }), { headers: { 'Content-Type': 'text/event-stream; charset=utf-8' } });
};

test('question boundaries use Unicode code points and trim whitespace', () => {
  assert.equal(codePointLength('😀中'), 2);
  assert.equal(normalizeQuestion(' \n😀\t '), '😀');
  assert.equal(normalizeQuestion('😀'.repeat(1000)).length, 2000);
  assert.throws(() => normalizeQuestion('😀'.repeat(1001)));
  for (const invalid of ['', ' \n ', null, 1, [], 'bad\u0000text', 'bad\rtext']) assert.throws(() => normalizeQuestion(invalid));
  assert.equal(normalizeQuestion('a\nb\tc'), 'a\nb\tc');
});

test('history sends only three complete recent turns in alternating order', () => {
  const turns = Array.from({ length: 5 }, (_, i) => ({ question: `q${i}`, answer: `a${i}` }));
  const history = buildHistory(turns);
  assert.deepEqual(history.map(item => item.content), ['q2', 'a2', 'q3', 'a3', 'q4', 'a4']);
  assert.deepEqual(history.map(item => item.role), ['user', 'assistant', 'user', 'assistant', 'user', 'assistant']);
  assert.equal(turns.length, 5);
});

test('history 6000-code-point budget removes oldest whole turns', () => {
  const turns = Array.from({ length: 3 }, () => ({ question: '😀'.repeat(1000), answer: '好'.repeat(1000) }));
  assert.equal(buildHistory(turns).length, 6);
  turns[2].answer += 'a';
  assert.equal(buildHistory(turns).length, 4);
  assert.throws(() => buildHistory([{ question: 'q', answer: '' }]));
  assert.throws(() => buildHistory([{ question: 'q', answer: 'a'.repeat(2001) }]));
});

test('request sends current question once, accepts JSON without a second POST', async () => {
  let calls = 0;
  const result = await requestResumeAnswer({
    question: ' current ', turns: [{ question: 'past', answer: 'answer' }],
    fetchImpl: async (url, options) => {
      calls++;
      assert.equal(url, '/api/v1/resume/chat');
      assert.equal(options.method, 'POST');
      assert.equal(options.headers.Accept, 'text/event-stream');
      assert.deepEqual(JSON.parse(options.body), { question: 'current', history: [{ role: 'user', content: 'past' }, { role: 'assistant', content: 'answer' }] });
      return Response.json({ request_id: responseId, answer: '完整回答' });
    },
  });
  assert.equal(calls, 1);
  assert.equal(result.answer, '完整回答');
});

test('SSE parses split UTF-8 and CRLF, and commits only done answer', async () => {
  const drafts = [];
  const result = await requestResumeAnswer({ question: 'q', onDelta: value => drafts.push(value),
    fetchImpl: streamingFetch(': heartbeat\r\n\r\n' + event('delta', { delta: '你好😀' }) + event('delta', { delta: '呀' }) + event('done', { answer: '你好😀呀' }), 1),
  });
  assert.deepEqual(drafts, ['你好😀', '你好😀呀']);
  assert.equal(result.answer, '你好😀呀');
});

test('interrupted stream rejects after draft and never returns partial answer', async () => {
  const drafts = [];
  await assert.rejects(requestResumeAnswer({ question: 'q', onDelta: value => drafts.push(value), fetchImpl: streamingFetch(event('delta', { delta: '未完成' })) }), { code: 'AI_INVALID_RESPONSE' });
  assert.deepEqual(drafts, ['未完成']);
});

test('stream terminal error is friendly and never retries', async () => {
  let calls = 0;
  const fetchResponse = streamingFetch(event('delta', { delta: '未完成' }) + event('error', { error: { code: 'AI_TIMEOUT', message: 'unsafe internal details', retryable: true } }));
  await assert.rejects(requestResumeAnswer({ question: 'q', fetchImpl: (...args) => { calls++; return fetchResponse(...args); } }), error => error.code === 'AI_TIMEOUT' && error.retryable && !error.message.includes('unsafe'));
  assert.equal(calls, 1);
});

test('HTTP errors, unavailable backend and invalid success format are safe', async () => {
  let calls = 0;
  await assert.rejects(requestResumeAnswer({ question: 'q', fetchImpl: async () => {
    calls++;
    return Response.json({ error: { code: 'RESUME_UNAVAILABLE', message: '/private/server/path', retryable: false } }, { status: 503 });
  } }), error => error.code === 'RESUME_UNAVAILABLE' && !error.message.includes('/private'));
  assert.equal(calls, 1);
  await assert.rejects(requestResumeAnswer({ question: 'q', fetchImpl: async () => new Response('<html>proxy error</html>', { status: 502 }) }), { code: 'CONNECTION_ERROR' });
  await assert.rejects(requestResumeAnswer({ question: 'q', fetchImpl: async () => new Response('<html>SPA fallback</html>', { headers: { 'Content-Type': 'text/html' } }) }), { code: 'CONNECTION_ERROR' });
  await assert.rejects(requestResumeAnswer({ question: 'q', fetchImpl: async () => Response.json({ request_id: responseId, answer: ' ' }) }), { code: 'AI_INVALID_RESPONSE' });
});

test('invalid and oversized SSE answers reject instead of truncating', async () => {
  for (const payload of [event('done', { answer: '😀'.repeat(2001) }), event('delta', { delta: 'a'.repeat(2001) }), 'event: delta\ndata: not-json\n\n', event('done', { answer: '' })]) {
    await assert.rejects(requestResumeAnswer({ question: 'q', fetchImpl: streamingFetch(payload) }), { code: 'AI_INVALID_RESPONSE' });
  }
  await assert.rejects(requestResumeAnswer({ question: 'q', fetchImpl: streamingFetch(event('delta', { delta: 'a' }) + event('done', { request_id: 'other', answer: 'b' })) }), { code: 'AI_INVALID_RESPONSE' });
});

test('HTML is returned as plain text for Vue interpolation', async () => {
  const html = '<img src=x onerror=alert(1)>';
  const result = await requestResumeAnswer({ question: 'q', fetchImpl: streamingFetch(event('done', { answer: html })) });
  assert.equal(result.answer, html);
});

test('aborted requests never commit even if transport ignores cancellation', async () => {
  const controller = new AbortController();
  let resolveFetch;
  const promise = requestResumeAnswer({ question: 'q', signal: controller.signal, fetchImpl: () => new Promise(resolve => { resolveFetch = resolve; }) });
  controller.abort();
  resolveFetch(Response.json({ request_id: responseId, answer: 'late answer' }));
  await assert.rejects(promise, { name: 'AbortError' });
});

test('pre-abort skips POST, timeout aborts a single POST', async () => {
  const controller = new AbortController();
  controller.abort();
  let calls = 0;
  await assert.rejects(requestResumeAnswer({ question: 'q', signal: controller.signal, fetchImpl: async () => { calls++; } }), { name: 'AbortError' });
  assert.equal(calls, 0);
  await assert.rejects(requestResumeAnswer({ question: 'q', timeoutMs: 5, fetchImpl: (_, { signal }) => {
    calls++;
    return new Promise((resolve, reject) => signal.addEventListener('abort', () => reject(new DOMException('', 'AbortError'))));
  } }), { code: 'AI_TIMEOUT' });
  assert.equal(calls, 1);
});
