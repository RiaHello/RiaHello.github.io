export const codePointLength = (text) => Array.from(text).length;
const forbiddenControls = /[\u0000-\u0008\u000b-\u001f]/u;

const messages = {
  RESUME_UNAVAILABLE: '公开简历暂未准备好，请稍后再来。',
  RATE_LIMITED: '提问有点频繁，请稍后手动重试。',
  DAILY_QUOTA_EXCEEDED: '今天的问答额度已用完，请明天再来。',
  LIMITER_UNAVAILABLE: '简历助手暂时不可用，请稍后手动重试。',
  AI_UNAVAILABLE: 'AI 服务暂时繁忙，请稍后手动重试。',
  AI_CONFIGURATION_ERROR: '简历助手暂时不可用，请稍后再来。',
  AI_TIMEOUT: '这次回答等待超时，请稍后手动重试。',
  AI_INVALID_RESPONSE: '这次未能生成完整回答，请稍后再试。',
  VALIDATION_ERROR: '问题格式不正确，请检查后再发送。',
  PAYLOAD_TOO_LARGE: '提问内容过长，请缩短后再发送。',
};

export class ChatError extends Error {
  constructor(code, message, retryable = false) {
    super(message || messages[code] || '简历助手暂时无法连接，请稍后再试。');
    this.name = 'ChatError';
    this.code = code;
    this.retryable = retryable;
  }
}

function normalizedText(value, maxLength) {
  if (typeof value !== 'string') return null;
  const text = value.trim();
  if (!text || codePointLength(text) > maxLength || forbiddenControls.test(text)) return null;
  return text;
}

export function normalizeQuestion(value) {
  const question = normalizedText(value, 1000);
  if (!question) throw new ChatError('VALIDATION_ERROR', '请输入 1～1000 个字符的问题，不能包含特殊控制字符。');
  return question;
}

// Only complete, validated turns are eligible for the next request.
export function buildHistory(turns) {
  const recent = turns.slice(-3).map(({ question, answer }) => {
    const user = normalizedText(question, 1000);
    const assistant = normalizedText(answer, 2000);
    if (!user || !assistant) throw new ChatError('VALIDATION_ERROR');
    return [{ role: 'user', content: user }, { role: 'assistant', content: assistant }];
  });
  const length = () => recent.flat().reduce((sum, item) => sum + codePointLength(item.content), 0);
  while (length() > 6000) recent.shift();
  return recent.flat();
}

function readAnswer(data) {
  const answer = normalizedText(data?.answer, 2000);
  if (!answer || typeof data?.request_id !== 'string' || !data.request_id) {
    throw new ChatError('AI_INVALID_RESPONSE');
  }
  return { answer, request_id: data.request_id };
}

function responseError(data) {
  return new ChatError(data?.error?.code || 'CONNECTION_ERROR', undefined, data?.error?.retryable === true);
}

async function readStream(response, onDelta, signal) {
  if (!response.body) throw new ChatError('AI_INVALID_RESPONSE');
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8', { fatal: true });
  let buffer = '';
  let draft = '';
  let requestId;
  try {
    while (true) {
      const chunk = await reader.read();
      signal.throwIfAborted();
      buffer += decoder.decode(chunk.value, { stream: !chunk.done });
      if (buffer.length > 65536) throw new ChatError('AI_INVALID_RESPONSE');
      let separator;
      while ((separator = /\r?\n\r?\n/u.exec(buffer))) {
        const event = buffer.slice(0, separator.index);
        buffer = buffer.slice(separator.index + separator[0].length);
        let type = 'message';
        const dataLines = [];
        for (const line of event.split(/\r?\n/u)) {
          if (line.startsWith('event:')) type = line.slice(6).trim();
          if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /u, ''));
        }
        if (!dataLines.length) continue; // SSE heartbeat/comment.
        if (!['delta', 'done', 'error'].includes(type)) throw new ChatError('AI_INVALID_RESPONSE');
        let data;
        try { data = JSON.parse(dataLines.join('\n')); }
        catch { throw new ChatError('AI_INVALID_RESPONSE'); }
        if (typeof data?.request_id !== 'string' || !data.request_id || (requestId && data.request_id !== requestId)) {
          throw new ChatError('AI_INVALID_RESPONSE');
        }
        requestId = data.request_id;
        if (type === 'error') throw responseError(data);
        if (type === 'done') return readAnswer(data);
        if (typeof data.delta !== 'string' || forbiddenControls.test(data.delta)) throw new ChatError('AI_INVALID_RESPONSE');
        draft += data.delta;
        if (codePointLength(draft) > 2000) throw new ChatError('AI_INVALID_RESPONSE');
        onDelta(draft);
      }
      if (chunk.done) throw new ChatError('AI_INVALID_RESPONSE'); // EOF never commits a partial answer.
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export async function requestResumeAnswer({ question, turns = [], signal, onDelta = () => {}, fetchImpl = fetch, timeoutMs = 40000 }) {
  const body = JSON.stringify({ question: normalizeQuestion(question), history: buildHistory(turns) });
  if (new TextEncoder().encode(body).length > 49152) throw new ChatError('PAYLOAD_TOO_LARGE');
  const controller = new AbortController();
  const abort = () => controller.abort(signal.reason);
  signal?.addEventListener('abort', abort, { once: true });
  if (signal?.aborted) abort();
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  try {
    controller.signal.throwIfAborted();
    const response = await fetchImpl('/api/v1/resume/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body,
      signal: controller.signal,
      cache: 'no-store',
    });
    controller.signal.throwIfAborted();
    if (!response.ok) {
      const error = await response.json().catch(() => null);
      throw responseError(error);
    }
    const type = response.headers.get('Content-Type')?.split(';')[0].trim().toLowerCase();
    if (type === 'text/event-stream') return await readStream(response, onDelta, controller.signal);
    if (type !== 'application/json') throw new ChatError('CONNECTION_ERROR');
    const result = readAnswer(await response.json());
    controller.signal.throwIfAborted();
    return result;
  } catch (error) {
    if (timedOut) throw new ChatError('AI_TIMEOUT', undefined, true);
    if (controller.signal.aborted) throw new DOMException('Request cancelled', 'AbortError');
    if (error instanceof ChatError) throw error;
    throw new ChatError('CONNECTION_ERROR');
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', abort);
  }
}
