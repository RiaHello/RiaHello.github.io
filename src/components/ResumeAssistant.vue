<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { codePointLength, normalizeQuestion, requestResumeAnswer } from '../lib/resume-chat.js';

const question = ref('');
const turns = ref([]);
const busy = ref(false);
const pendingQuestion = ref('');
const draft = ref('');
const error = ref('');
const notice = ref('');
const input = ref(null);
const conversationRegion = ref(null);
const conversationList = ref(null);
let activeController;
let generation = 0;
const composing = ref(false);
let resizeObserver;
const length = computed(() => codePointLength(question.value.trim()));
const canSend = computed(() => !busy.value && length.value > 0 && length.value <= 1000);
const canClear = computed(() => question.value.length || turns.value.length || error.value || busy.value || notice.value);

let conversationObserver;
let conversationLayoutQueued = false;
let conversationDisposed = false;
let followConversation = true;

function trackConversationScroll() {
  const region = conversationRegion.value;
  if (region) followConversation = region.scrollHeight - region.scrollTop - region.clientHeight <= 32;
}

async function queueConversationLayout() {
  if (conversationLayoutQueued || conversationDisposed) return;
  conversationLayoutQueued = true;
  await nextTick();
  conversationLayoutQueued = false;
  if (conversationDisposed) return;
  const region = conversationRegion.value;
  const recent = Array.from(conversationList.value?.children || []).slice(-3);
  if (!region || !recent.length) return;
  const height = Math.ceil(recent.at(-1).getBoundingClientRect().bottom - recent[0].getBoundingClientRect().top);
  region.style.setProperty('--conversation-height', `${height}px`);
  if (followConversation) region.scrollTop = region.scrollHeight;
}

watch(conversationList, (list) => {
  conversationObserver?.disconnect();
  if (!list) return;
  conversationObserver = new ResizeObserver(queueConversationLayout);
  conversationObserver.observe(list);
  queueConversationLayout();
}, { flush: 'post' });
watch([() => turns.value.length, busy, draft], queueConversationLayout, { flush: 'post' });

// Vue adaptation of the supplied TextType: fade in, pause, then backspace.
const hintCharacters = Array.from('有什么问题就问问我吧～');
const hintCount = ref(0);
const hintInView = ref(false);
const documentVisible = ref(!document.hidden);
const reduceMotion = ref(false);
const hintVisible = computed(() => !question.value && !composing.value && !busy.value);
const hintActive = computed(() => hintVisible.value && hintInView.value && documentVisible.value && !reduceMotion.value);
let hintTimer;
let hintDueAt = 0;
let hintRemaining = 75;
let hintDeleting = false;
let hintDisposed = false;
let hintObserver;
let motionQuery;

function pauseHint() {
  if (hintTimer === undefined) return;
  hintRemaining = Math.max(0, hintDueAt - performance.now());
  clearTimeout(hintTimer);
  hintTimer = undefined;
}

function scheduleHint() {
  if (hintDisposed || !hintActive.value || hintTimer !== undefined) return;
  hintDueAt = performance.now() + hintRemaining;
  hintTimer = setTimeout(() => {
    hintTimer = undefined;
    if (hintDisposed || !hintActive.value) return;
    if (hintCount.value === hintCharacters.length) hintDeleting = true;
    hintCount.value += hintDeleting ? -1 : 1;
    if (hintCount.value === 0) hintDeleting = false;
    hintRemaining = hintCount.value === hintCharacters.length ? 1500 : hintDeleting ? 50 : 75;
    scheduleHint();
  }, hintRemaining);
}

const syncDocumentVisibility = () => { documentVisible.value = !document.hidden; };
const syncMotionPreference = () => {
  pauseHint();
  reduceMotion.value = motionQuery.matches;
  hintCount.value = reduceMotion.value ? hintCharacters.length : 0;
  hintDeleting = false;
  hintRemaining = 75;
  scheduleHint();
};
watch(hintActive, (active) => { if (active) scheduleHint(); else pauseHint(); }, { flush: 'sync' });

function resizeInput() {
  const textarea = input.value;
  if (!textarea) return;
  textarea.style.overflowY = 'hidden';
  textarea.style.height = 'auto';
  const height = textarea.scrollHeight;
  textarea.style.height = `${Math.min(height, 180)}px`;
  textarea.style.overflowY = height > 180 ? 'auto' : 'hidden';
}

watch(question, resizeInput, { flush: 'post' });
onMounted(() => {
  resizeInput();
  let previousWidth;
  resizeObserver = new ResizeObserver(([entry]) => {
    if (entry.contentRect.width === previousWidth) return;
    previousWidth = entry.contentRect.width;
    resizeInput();
  });
  resizeObserver.observe(input.value);
  motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  syncMotionPreference();
  motionQuery.addEventListener('change', syncMotionPreference);
  document.addEventListener('visibilitychange', syncDocumentVisibility);
  hintObserver = new IntersectionObserver(([entry]) => {
    hintInView.value = entry.isIntersecting && entry.intersectionRatio > 0;
  });
  hintObserver.observe(input.value);
  window.addEventListener('resize', queueConversationLayout);
});

function cancel() {
  generation += 1;
  activeController?.abort();
  activeController = undefined;
  busy.value = false;
  draft.value = '';
  pendingQuestion.value = '';
}

function stop() {
  cancel();
  notice.value = '已停止生成，问题已保留。';
}

function clear() {
  cancel();
  followConversation = true;
  turns.value = [];
  question.value = '';
  error.value = '';
  notice.value = '';
  nextTick(() => input.value?.focus());
}

function onEnter(event) {
  if (event.shiftKey || event.isComposing || composing.value || event.keyCode === 229) return;
  event.preventDefault();
  send();
}

async function send() {
  if (busy.value) return;
  error.value = '';
  notice.value = '';
  let text;
  try { text = normalizeQuestion(question.value); }
  catch (failure) { error.value = failure.message; return; }
  followConversation = true;
  question.value = text;
  pendingQuestion.value = text;
  busy.value = true;
  draft.value = '';
  const token = ++generation;
  const controller = new AbortController();
  activeController = controller;
  try {
    const result = await requestResumeAnswer({
      question: text,
      turns: turns.value,
      signal: controller.signal,
      onDelta: (value) => { if (token === generation) draft.value = value; },
    });
    if (token !== generation) return;
    turns.value.push({ question: text, answer: result.answer, requestId: result.request_id });
    question.value = '';
    notice.value = '回答已完成。';
  } catch (failure) {
    if (token !== generation) return;
    error.value = failure.name === 'AbortError' ? '生成已停止，问题已保留。' : failure.message;
  } finally {
    if (token === generation) {
      busy.value = false;
      draft.value = '';
      pendingQuestion.value = '';
      activeController = undefined;
    }
  }
}

onBeforeUnmount(() => {
  conversationDisposed = true;
  conversationObserver?.disconnect();
  window.removeEventListener('resize', queueConversationLayout);
  hintDisposed = true;
  pauseHint();
  hintObserver?.disconnect();
  motionQuery?.removeEventListener('change', syncMotionPreference);
  document.removeEventListener('visibilitychange', syncDocumentVisibility);
  resizeObserver?.disconnect();
  cancel();
});
</script>

<template>
  <section class="resume-assistant" aria-label="AI 简历助手">
    <div v-if="turns.length || busy" ref="conversationRegion" class="conversation-scroll" role="region" aria-label="问答记录，可滚动查看历史" tabindex="0" @scroll="trackConversationScroll">
    <ol ref="conversationList" class="conversation">
      <li v-for="(turn, index) in turns" :key="`${turn.requestId}-${index}`" class="conversation-turn">
        <div class="message message-user"><span class="message-author">你</span><p>{{ turn.question }}</p></div>
        <div class="message message-assistant"><span class="message-author">简历助手</span><p>{{ turn.answer }}</p></div>
      </li>
      <li v-if="busy" class="conversation-turn" aria-busy="true">
        <div class="message message-user"><span class="message-author">你</span><p>{{ pendingQuestion }}</p></div>
        <div class="message message-assistant message-draft"><span class="message-author">简历助手 · {{ draft ? '正在生成，尚未完成' : '正在思考' }}</span><p>{{ draft || '正在查阅公开简历…' }}</p></div>
      </li>
    </ol>
    </div>

    <form class="question-form" @submit.prevent="send">
      <label class="visually-hidden" for="resume-question">想了解什么？</label>
      <div class="input-bar">
        <textarea id="resume-question" ref="input" v-model="question" :class="{ 'textarea--hint': hintVisible }" rows="1" :readonly="busy" :aria-invalid="length > 1000" :aria-describedby="length > 1000 ? 'resume-length-error' : undefined" @keydown.enter="onEnter" @compositionstart="composing = true" @compositionend="composing = false"></textarea>
        <div v-show="hintVisible" class="typing-hint" :class="{ 'typing-hint--paused': !hintActive, 'typing-hint--static': reduceMotion }" :style="{ '--hint-count': hintCount }" aria-hidden="true">
          <span v-for="(character, index) in hintCharacters.slice(0, hintCount)" :key="index" class="typing-hint-character">{{ character }}</span><span class="typing-hint-cursor"></span>
        </div>
        <button v-if="busy" type="button" class="send-button" aria-label="停止生成" title="停止生成" @click="stop"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="1" fill="currentColor" /></svg></button>
        <button v-else type="submit" class="send-button" :disabled="!canSend" aria-label="发送问题" title="发送问题"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5m-6 6 6-6 6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg></button>
      </div>
    </form>
    <div v-if="canClear || busy || notice" class="conversation-actions">
      <p v-if="busy || notice" class="assistant-status" role="status" aria-live="polite">{{ busy ? (draft ? '正在生成回答…' : '正在等待回答…') : notice }}</p>
      <button v-if="canClear" type="button" class="clear-button" @click="clear">清空对话</button>
    </div>
    <p v-if="length > 1000" id="resume-length-error" class="assistant-error" role="alert">问题不能超过 1000 个字符，当前 {{ length }} 个。</p>
    <p v-if="error" class="assistant-error" role="alert">{{ error }} 问题已保留，可修改后手动发送。</p>
  </section>
</template>

<style scoped>
.resume-assistant { cursor: auto; min-width: 0; }
.visually-hidden { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; border: 0; }
button, textarea { font: inherit; }
button { cursor: pointer; transition: border-color .18s ease, background .18s ease; }
button:disabled { opacity: .45; cursor: not-allowed; }
button:focus-visible { outline: 2px solid #b7ff3b; outline-offset: 3px; }
.conversation-scroll { max-height: min(60vh, var(--conversation-height, 60vh)); overflow-y: auto; overflow-x: hidden; overflow-anchor: none; overscroll-behavior-y: contain; scrollbar-gutter: stable; scrollbar-color: #526642 transparent; scrollbar-width: thin; margin-bottom: 1.5rem; }
.conversation-scroll:focus-visible { outline: 2px solid #b7ff3b; outline-offset: 4px; }
.conversation { display: flex; flex-direction: column; gap: 1.4rem; padding: 0; margin: 0; list-style: none; }
.conversation-turn { min-width: 0; }
.message { padding: 1rem 1.1rem; border-radius: 12px; min-width: 0; }
.message-user { background: #20271b; margin-left: 8%; }
.message-assistant { margin: .5rem 8% 0 0; border: 1px solid #303a29; }
.message-author { color: #b7ff3b; font-size: .75rem; }
.message p { white-space: pre-wrap; overflow-wrap: anywhere; color: #e2e6de; font-size: .93rem; line-height: 1.8; margin: .45rem 0 0; }
.message-draft { border-style: dashed; }
.input-bar { position: relative; background: #10140e; border: 1px solid #47523e; border-radius: 14px; }
.input-bar:focus-within { border-color: #b7ff3b; }
textarea { display: block; width: 100%; box-sizing: border-box; resize: none; min-height: 52px; max-height: 180px; overflow-y: hidden; color: #fff; background: transparent; border: 0; border-radius: inherit; padding: 14px 62px 14px 16px; line-height: 24px; font-size: 1rem; }
textarea:focus { outline: none; }
.textarea--hint { caret-color: transparent; }
.typing-hint { position: absolute; top: 14px; left: 16px; right: 62px; height: 24px; color: #9ca3af; font-size: 14px; line-height: 24px; white-space: nowrap; pointer-events: none; user-select: none; }
.typing-hint-character { display: inline-block; width: 1em; animation: hint-character-in 360ms cubic-bezier(.25, 1, .5, 1) both; }
.typing-hint-cursor { position: absolute; top: 4px; left: 1px; width: 2px; height: 16px; border-radius: 1px; background: currentColor; transform: translateX(calc(var(--hint-count) * 1em)); transition: transform 120ms cubic-bezier(.22, 1, .36, 1); animation: hint-cursor-blink 1s ease-in-out infinite; }
.typing-hint--paused .typing-hint-character, .typing-hint--paused .typing-hint-cursor { animation-play-state: paused; }
.typing-hint--static .typing-hint-character, .typing-hint--static .typing-hint-cursor { animation: none; transition: none; }
@keyframes hint-character-in { from { opacity: 0; } to { opacity: 1; } }
@keyframes hint-cursor-blink { 0%, 35%, 100% { opacity: 1; } 55%, 75% { opacity: 0; } }
@media (prefers-reduced-motion: reduce) {
  .typing-hint-character, .typing-hint-cursor { animation: none; transition: none; }
}
.conversation-actions { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-top: .4rem; }
.clear-button { margin-left: auto; flex-shrink: 0; min-height: 40px; padding: .4rem .2rem; font-size: .78rem; color: #b7c2ad; background: transparent; border: 0; }
.clear-button:hover { color: #b7ff3b; }
.send-button { position: absolute; right: 4px; bottom: 4px; display: grid; place-items: center; width: 44px; height: 44px; padding: 0; border-radius: 10px; color: #142000; background: #b7ff3b; border: 0; }
.send-button svg { width: 22px; height: 22px; }
.assistant-error { color: #ffc6ad; background: #2a1e17; border-radius: 8px; padding: .8rem 1rem; line-height: 1.7; font-size: .85rem; overflow-wrap: anywhere; }
.assistant-status { margin: 0; font-size: .78rem; line-height: 1.6; color: #b7c2ad; }
@media (max-width: 600px) {
  .message { padding: .8rem; }
  .message-user { margin-left: 4%; }
  .message-assistant { margin-right: 4%; }
}
</style>
