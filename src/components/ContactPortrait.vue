<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import TextPressure from './TextPressure.vue';
import portraitVideo from '../assets/contact-gaze.mp4';
import portraitPoster from '../assets/contact-portrait-poster.jpg';

const props = withDefaults(defineProps<{ active?: boolean }>(), { active: true });
const emit = defineEmits<{ goHome: []; goResume: [] }>();
const email = 'rudrakshaishere@gmail.com';
const wechat = 'Ria_is_here';
const introduction = '我是石耳，一个热爱技术与分享的硬地骇客（Indie Hacker)，来和我聊聊吧～';
// Keep the English name together in both the typewriter and its layout spacer.
const displayIntroduction = introduction.replace('Indie Hacker', 'Indie\u00a0Hacker');
const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
const reducedMotion = ref(motionPreference.matches);
const visibleLetters = ref(reducedMotion.value ? introduction.length : 0);
const typedIntroduction = computed(() => displayIntroduction.slice(0, visibleLetters.value));
const actionsVisible = ref(reducedMotion.value);
const video = ref<HTMLVideoElement | null>(null);
const mediaReady = ref(false);
const mediaFailed = ref(false);
const duration = ref(0);
const targetTime = ref(0);
const videoFps = 60;
const maximumTime = computed(() => Math.max(0, duration.value - 1 / videoFps));
// The prepared clip is one continuous left → front → right sequence.
// These are exact frame positions; there is no timeline jump at the center.
const gazeFrames = { left: 10 / videoFps, front: 120 / videoFps, right: 190 / videoFps };
// Keep the neutral zone exactly 45–50% of the viewport, regardless of face layout.
const frontZone = { left: 0.45, right: 0.5 };
const targetGaze = ref(0);
let currentGaze = 0;
let gazeFrame = 0;
let gazeTick = 0;
const menuOpen = ref(false);
const menuButton = ref<HTMLButtonElement | null>(null);
const menuDialog = ref<HTMLElement | null>(null);
const homeLink = ref<HTMLAnchorElement | null>(null);
const feedback = ref('');
const manualCopy = ref('');
let disposed = false;
let copyRequest = 0;
let revealTimer: ReturnType<typeof setTimeout> | undefined;
let typeTimer: ReturnType<typeof setTimeout> | undefined;
let seekPending = false;
let lastMouseX: number | null = null;
let touch: { id: number; x: number; y: number; horizontal: boolean } | null = null;

function clearTyping() {
  clearTimeout(typeTimer);
  clearTimeout(revealTimer);
}

function typeNextLetter() {
  if (disposed || !props.active) return;
  visibleLetters.value += 1;
  if (visibleLetters.value < introduction.length) typeTimer = setTimeout(typeNextLetter, 38);
}

function updateMotionPreference(event: MediaQueryListEvent) {
  reducedMotion.value = event.matches;
  lastMouseX = null;
  if (event.matches) {
    clearTyping();
    visibleLetters.value = introduction.length;
    actionsVisible.value = true;
    setGaze(targetGaze.value);
  }
}

// Only one seek may be in flight. New input replaces the destination, not the seek queue.
function flushSeek() {
  if (disposed || seekPending || mediaFailed.value || !duration.value) return;
  const player = video.value;
  if (!player || player.seeking || Math.abs(player.currentTime - targetTime.value) < 0.5 / videoFps) return;
  seekPending = true;
  player.currentTime = targetTime.value;
}

function onSeeked() {
  seekPending = false;
  if (!disposed && !mediaFailed.value) mediaReady.value = true;
  flushSeek();
}

function onLoadedData() {
  if (video.value && !video.value.seeking && Math.abs(video.value.currentTime - targetTime.value) < 0.5 / videoFps) {
    mediaReady.value = true;
  }
}

function onMetadata() {
  if (video.value && Number.isFinite(video.value.duration)) {
    duration.value = video.value.duration;
    setTime(timeForGaze(currentGaze));
  }
}

function onMediaError() {
  mediaFailed.value = true;
  mediaReady.value = false;
  seekPending = false;
  cancelAnimationFrame(gazeFrame);
  gazeFrame = 0;
}

function setTime(time: number) {
  if (mediaFailed.value) return;
  // Seek only when the displayed frame changes, not on every pointer event.
  targetTime.value = Math.min(maximumTime.value, Math.max(0, Math.round(time * videoFps) / videoFps + 0.0001));
  flushSeek();
}

function timeForGaze(gaze: number) {
  if (gaze <= 0) return gazeFrames.front + gaze * (gazeFrames.front - gazeFrames.left);
  return gazeFrames.front + gaze * (gazeFrames.right - gazeFrames.front);
}

function animateGaze(now: number) {
  gazeFrame = 0;
  if (disposed || !props.active || mediaFailed.value) return;
  const elapsed = Math.min((now - gazeTick) / 1000, 0.05);
  gazeTick = now;
  const remaining = targetGaze.value - currentGaze;
  currentGaze = Math.abs(remaining) < 0.001
    ? targetGaze.value
    : currentGaze + remaining * (1 - Math.exp(-elapsed / 0.035));
  setTime(timeForGaze(currentGaze));
  if (currentGaze !== targetGaze.value) gazeFrame = requestAnimationFrame(animateGaze);
}

function setGaze(gaze: number) {
  if (mediaFailed.value) return;
  const nextGaze = Math.min(1, Math.max(-1, gaze));
  // Holding the front zone keeps one sharp frame, without restarting animation.
  if (nextGaze === targetGaze.value && currentGaze === nextGaze) return;
  targetGaze.value = nextGaze;
  if (reducedMotion.value) {
    cancelAnimationFrame(gazeFrame);
    gazeFrame = 0;
    currentGaze = targetGaze.value;
    setTime(timeForGaze(currentGaze));
  } else if (!gazeFrame) {
    gazeTick = performance.now();
    gazeFrame = requestAnimationFrame(animateGaze);
  }
}

function lookAtPointer(clientX: number) {
  const width = window.innerWidth;
  if (width <= 0 || !Number.isFinite(clientX)) return;
  const leftEdge = width * frontZone.left;
  const rightEdge = width * frontZone.right;
  if (clientX < leftEdge) {
    setGaze((clientX - leftEdge) / Math.max(1, leftEdge));
  } else if (clientX > rightEdge) {
    setGaze((clientX - rightEdge) / Math.max(1, width - rightEdge));
  } else {
    setGaze(0);
  }
}

function onPointerDown(event: PointerEvent) {
  if (event.pointerType === 'mouse' || !(event.target as Element).closest('.portrait-stage')) return;
  touch = { id: event.pointerId, x: event.clientX, y: event.clientY, horizontal: false };
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
}

function onPointerMove(event: PointerEvent) {
  if (!props.active || menuOpen.value) return;
  if (event.pointerType === 'mouse') {
    if (reducedMotion.value) {
      lastMouseX = null;
      return;
    }
    lastMouseX = event.clientX;
    lookAtPointer(event.clientX);
  } else if (touch?.id === event.pointerId) {
    const dx = event.clientX - touch.x;
    const dy = event.clientY - touch.y;
    if (!touch.horizontal) {
      if (Math.abs(dy) > Math.abs(dx) && Math.abs(dy) > 6) { touch = null; return; }
      if (Math.abs(dx) < 6) return;
      touch.horizontal = true;
    }
    lookAtPointer(event.clientX);
  }
}

async function copyContact(text: string, label: string) {
  const request = ++copyRequest;
  feedback.value = `正在复制${label}…`;
  manualCopy.value = '';
  try {
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
    await navigator.clipboard.writeText(text);
    if (!disposed && request === copyRequest) feedback.value = `${label}已复制，期待你的消息。`;
  } catch {
    if (!disposed && request === copyRequest) {
      feedback.value = `暂时无法复制，请手动复制${label}：`;
      manualCopy.value = text;
    }
  }
}

async function openMenu() {
  menuOpen.value = true;
  await nextTick();
  menuDialog.value?.querySelector<HTMLButtonElement>('button')?.focus();
}

function closeMenu(restoreFocus = true) {
  menuOpen.value = false;
  if (restoreFocus) nextTick(() => menuButton.value?.focus());
}

function onResize() {
  if (!props.active) return;
  if (window.innerWidth > 900 && menuOpen.value) {
    closeMenu(false);
    nextTick(() => homeLink.value?.focus());
  }
  if (!menuOpen.value && !reducedMotion.value && lastMouseX !== null) lookAtPointer(lastMouseX);
}

function navigate(page: 'home' | 'resume') {
  closeMenu();
  if (page === 'home') emit('goHome');
  else emit('goResume');
}

function onMenuKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') { event.preventDefault(); closeMenu(); }
  if (event.key !== 'Tab') return;
  const items = menuDialog.value?.querySelectorAll<HTMLElement>('a, button');
  if (!items?.length) return;
  const first = items[0];
  const last = items[items.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}

function updateActivity() {
  clearTyping();
  cancelAnimationFrame(gazeFrame);
  gazeFrame = 0;
  lastMouseX = null;
  touch = null;
  if (!props.active) {
    menuOpen.value = false;
    // Reset once to the sharp front frame; no pointer or animation loop runs hidden.
    currentGaze = 0;
    targetGaze.value = 0;
    if (duration.value) setTime(timeForGaze(0));
    return;
  }
  if (reducedMotion.value) {
    visibleLetters.value = introduction.length;
    actionsVisible.value = true;
  } else {
    if (!actionsVisible.value) revealTimer = setTimeout(() => { actionsVisible.value = true; }, 400);
    if (visibleLetters.value < introduction.length) typeTimer = setTimeout(typeNextLetter, 600);
  }
}

watch(() => props.active, updateActivity);

onMounted(() => {
  motionPreference.addEventListener('change', updateMotionPreference);
  window.addEventListener('resize', onResize);
  // The handwritten background must also be ready while the page is hidden.
  document.fonts.load('400 16px "Contact Allura"').catch(() => {});
  updateActivity();
});

onUnmounted(() => {
  disposed = true;
  clearTyping();
  cancelAnimationFrame(gazeFrame);
  motionPreference.removeEventListener('change', updateMotionPreference);
  window.removeEventListener('resize', onResize);
});
</script>

<template>
  <main class="contact-page" :class="{ 'menu-is-open': menuOpen }"
    @pointerdown="onPointerDown" @pointermove="onPointerMove"
    @pointerup="touch = null" @pointercancel="touch = null" @pointerleave="lastMouseX = null">
    <div class="contact-scene" :inert="menuOpen">
      <div class="portrait-stage" aria-hidden="true">
        <img class="portrait-media" :src="portraitPoster" alt="" />
        <video ref="video" class="portrait-media" :class="{ 'video-ready': mediaReady && !mediaFailed }"
          :src="portraitVideo" :poster="portraitPoster" muted playsinline preload="auto"
          @loadedmetadata="onMetadata" @loadeddata="onLoadedData" @seeked="onSeeked" @error="onMediaError"></video>
      </div>
      <div class="portrait-shade" aria-hidden="true"></div>

      <header class="contact-header">
        <a ref="homeLink" class="ria-mark" href="#home" aria-label="RIA 首页" @click.prevent="navigate('home')">RIA<span></span></a>
        <nav class="desktop-nav" aria-label="主导航">
          <a href="#home" @click.prevent="navigate('home')">首页</a>
          <a href="#resume" @click.prevent="navigate('resume')">关于我</a>
          <a href="#contact" aria-current="page" @click.prevent>联系我<span class="nav-dot"></span></a>
        </nav>
        <button ref="menuButton" class="menu-toggle" aria-label="打开导航菜单" :aria-expanded="menuOpen"
          aria-controls="contact-menu" @click="openMenu"><span></span><span></span></button>
      </header>

      <section class="contact-content" aria-labelledby="contact-title">
        <div class="intro-ghost" aria-hidden="true"><span>Our story</span><span>is just beginning.</span></div>
        <h1 id="contact-title" aria-label="Let's talk."><TextPressure text="Let's talk." :active="active && !menuOpen" /></h1>
        <p class="sr-only">{{ introduction }}</p>
        <p class="introduction" aria-hidden="true">
          <span class="intro-spacer">{{ displayIntroduction }}</span>
          <span class="typed-intro">{{ typedIntroduction }}<span v-if="!reducedMotion && visibleLetters < introduction.length" class="typing-cursor">▏</span></span>
        </p>

        <div class="contact-actions" :class="{ 'actions-visible': actionsVisible }">
          <div class="action-row">
            <a class="pill primary-action" href="#resume" @click.prevent="navigate('resume')">聊聊项目 <span aria-hidden="true">↗</span></a>
            <button class="pill" @click="copyContact(wechat, '微信号')">加个微信 <span aria-hidden="true">＋</span></button>
            <a class="pill" href="https://github.com/RiaHello" target="_blank" rel="noopener noreferrer">看看 GitHub <span aria-hidden="true">↗</span></a>
          </div>
          <button class="email-button" :aria-label="`复制邮箱 ${email}`" @click="copyContact(email, '邮箱')">
            <span>{{ email }}</span>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M15 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h3"/></svg>
          </button>
          <div class="copy-feedback" role="status" aria-live="polite">
            <p>{{ feedback }}</p>
            <input v-if="manualCopy" class="manual-copy" :value="manualCopy" aria-label="手动复制联系信息" readonly
              @focus="($event.target as HTMLInputElement).select()" />
          </div>
        </div>
      </section>

      <footer class="contact-footer">
        <span class="footer-index" aria-hidden="true">03 / CONTACT</span>
      </footer>
    </div>

    <div v-if="menuOpen" id="contact-menu" ref="menuDialog" class="mobile-menu" role="dialog" aria-modal="true" aria-label="导航菜单" @keydown="onMenuKeydown">
      <div class="menu-top"><span class="ria-mark">RIA<span></span></span><button class="menu-close" aria-label="关闭导航菜单" @click="closeMenu()">关闭 <span aria-hidden="true">×</span></button></div>
      <nav aria-label="主导航">
        <a href="#home" @click.prevent="navigate('home')"><small>01</small>首页<span>↗</span></a>
        <a href="#resume" @click.prevent="navigate('resume')"><small>02</small>关于我<span>↗</span></a>
        <a href="#contact" aria-current="page" @click.prevent="closeMenu()"><small>03</small>联系我<span>↗</span></a>
      </nav>
    </div>
  </main>
</template>

<style scoped>
@font-face {
  font-family: 'Contact Allura';
  src: url('../assets/fonts/Allura-Latin.woff2') format('woff2');
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}
.contact-page { --ink: #171916; --paper: #f5f3ed; color: var(--paper); background: var(--ink); height: 100dvh; overflow-y: auto; overflow-x: hidden; cursor: auto; font-family: 'Inter', 'SF Pro Display', 'PingFang SC', sans-serif; }
.contact-scene { position: relative; min-height: max(740px, 100dvh); overflow: hidden; isolation: isolate; }
.portrait-stage { position: absolute; inset: 0; z-index: -3; touch-action: pan-y; }
.portrait-media { position: absolute; top: 0; left: 18%; width: 100%; height: 100%; object-fit: cover; object-position: center; }
video.portrait-media { opacity: 0; }
video.video-ready { opacity: 1; }
.portrait-shade { position: absolute; inset: 0; z-index: -2; pointer-events: none; background: linear-gradient(90deg, #171916 23%, rgba(23,25,22,.84) 36%, rgba(23,25,22,.3) 53%, transparent 69%), linear-gradient(0deg, rgba(23,25,22,.8), transparent 28%); }
.contact-header { display: flex; align-items: center; justify-content: space-between; height: 100px; padding: 0 clamp(40px, 5vw, 72px); }
.ria-mark { display: inline-flex; gap: 5px; align-items: baseline; font-size: 28px; font-weight: 800; letter-spacing: -2px; color: var(--paper); }
.ria-mark > span { width: 6px; height: 6px; background: #b7ff3b; border-radius: 50%; }
.desktop-nav { display: flex; align-items: center; gap: 38px; }
.desktop-nav a { display: flex; align-items: center; gap: 8px; color: #282b25; font-size: 13px; font-weight: 600; min-height: 44px; border-bottom: 1px solid transparent; }
.desktop-nav a:hover { border-bottom-color: currentColor; }
.nav-dot { width: 5px; height: 5px; background: #282b25; border-radius: 50%; }
.contact-content { position: relative; width: 560px; max-width: 49%; margin: clamp(115px, 18vh, 185px) 0 0 clamp(40px, 5vw, 72px); padding-bottom: 110px; }
.intro-ghost { position: absolute; z-index: -1; top: -78px; left: 36px; width: max-content; max-width: calc(100vw - 80px); color: #d3d2c8; opacity: .3; filter: blur(1px); font-family: 'Contact Allura', 'Snell Roundhand', 'Apple Chancery', cursive; font-size: clamp(58px, 5.6vw, 82px); line-height: .9; font-weight: 400; letter-spacing: 0; transform: rotate(-6deg); transform-origin: left center; pointer-events: none; user-select: none; }
.intro-ghost > span { display: block; white-space: nowrap; }
.intro-ghost > span + span { margin-left: .7em; }
h1 { font-size: clamp(64px, 7.5vw, 108px); line-height: 1.07; letter-spacing: -.07em; font-weight: 500; margin: 24px 0 25px -5px; white-space: nowrap; }
.introduction { position: relative; max-width: 430px; font-size: 16px; line-height: 1.85; color: #d4d2cb; letter-spacing: .025em; }
.intro-spacer { visibility: hidden; }
.typed-intro { position: absolute; inset: 0; }
.typing-cursor { color: #b7ff3b; animation: cursor-blink 1s step-end infinite; }
.contact-actions { margin-top: 29px; opacity: 0; visibility: hidden; transform: translateY(8px); transition: opacity .4s, transform .4s; }
.actions-visible { visibility: visible; opacity: 1; transform: none; }
.action-row { display: flex; flex-wrap: wrap; gap: 9px; max-width: 530px; }
.pill { min-height: 45px; display: inline-flex; align-items: center; justify-content: center; gap: 15px; padding: 0 17px; border-radius: 999px; color: #22251e; background: var(--paper); font-size: 12px; font-weight: 500; transition: transform .2s, background .2s; }
.pill > span { font-size: 17px; }
.pill:hover { color: var(--ink); background: #dffeab; transform: translateY(-3px); }
.email-button { display: flex; align-items: center; justify-content: space-between; gap: 24px; max-width: 100%; min-height: 46px; border: 1px solid #777c6c; border-radius: 999px; padding: 9px 18px; margin-top: 17px; color: #e1e2d9; font-size: 12px; letter-spacing: .025em; text-align: left; transition: border-color .2s; }
.email-button > span { overflow-wrap: anywhere; }
.email-button > svg { flex-shrink: 0; }
.email-button:hover { border-color: #b7ff3b; }
.copy-feedback { font-size: 12px; line-height: 1.6; color: #dffeab; margin-top: 12px; max-width: 430px; }
.manual-copy { display: block; margin-top: 5px; max-width: 100%; width: 320px; padding: 9px 12px; color: var(--paper); border: 1px solid #8b947e; border-radius: 6px; background: #171916; font: inherit; }
.contact-footer { position: absolute; bottom: 34px; right: clamp(40px, 5vw, 72px); }
.footer-index { color: #e5e7df; font-size: 9px; letter-spacing: .15em; }
.menu-toggle { display: none; }
a:focus-visible, button:focus-visible, input:focus-visible { outline: 2px solid #b7ff3b; outline-offset: 5px; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
.mobile-menu { position: fixed; inset: 0; z-index: 200; overflow: auto; background: #171916; color: var(--paper); padding: 24px; display: flex; flex-direction: column; }
.menu-top { display: flex; align-items: center; justify-content: space-between; }
.menu-close { color: var(--paper); min-height: 44px; font-size: 13px; display: flex; align-items: center; gap: 15px; }
.menu-close span { font-size: 30px; }
.mobile-menu nav { margin: auto 0; padding: 45px 0; }
.mobile-menu nav a { display: flex; align-items: center; gap: 15px; font-size: 32px; color: var(--paper); padding: 21px 0; border-bottom: 1px solid #ffffff26; }
.mobile-menu nav small { font-size: 10px; color: #b7ff3b; }
.mobile-menu nav a > span { margin-left: auto; font-size: 24px; }
.mobile-menu nav [aria-current] { color: #b7ff3b; }
.menu-is-open { overflow: hidden; }
@keyframes cursor-blink { 50% { opacity: 0; } }
@media (max-width: 900px) {
  .contact-scene { min-height: 100dvh; padding-top: 360px; }
  .portrait-stage { bottom: auto; height: 440px; }
  .portrait-media { left: 0; width: 100%; object-position: center top; }
  .portrait-shade { height: 460px; bottom: auto; background: linear-gradient(0deg, #171916 8%, rgba(23,25,22,.82) 18%, rgba(23,25,22,.2) 35%, transparent 52%); }
  .contact-header { position: absolute; top: 0; left: 0; right: 0; height: 82px; padding: 0 24px; }
  .contact-header .ria-mark { color: #272b23; font-size: 25px; }
  .contact-header .ria-mark > span { background: #4e6037; }
  .desktop-nav { display: none; }
  .menu-toggle { display: flex; flex-direction: column; justify-content: center; gap: 6px; width: 44px; height: 44px; align-items: center; color: #272b23; }
  .menu-toggle > span { width: 23px; height: 1.5px; background: currentColor; }
  .contact-content { margin: 0; padding: 0 24px 28px; width: 100%; max-width: none; }
  .intro-ghost { top: -32px; left: 40px; max-width: calc(100vw - 48px); font-size: clamp(36px, 10vw, 46px); opacity: .3; filter: blur(.65px); }
  .intro-ghost > span + span { margin-left: .45em; }
  h1 { font-size: 56px; margin: 16px 0 18px -2px; }
  .introduction { font-size: 14px; line-height: 1.85; max-width: 540px; }
  .contact-actions { margin-top: 23px; }
  .action-row { gap: 9px; max-width: 480px; }
  .pill { min-height: 44px; font-size: 12px; padding: 0 17px; gap: 18px; }
  .email-button { font-size: 11px; padding: 10px 15px; gap: 16px; margin-top: 14px; }
  .copy-feedback { margin-top: 8px; }
  .contact-footer { display: none; }
}
@media (max-width: 350px) {
  .contact-scene { padding-top: 315px; }
  .portrait-stage { height: 390px; }
  .portrait-shade { height: 410px; }
  .contact-content { padding-left: 20px; padding-right: 20px; }
  .contact-header { padding: 0 20px; }
  .intro-ghost { left: 36px; max-width: calc(100vw - 40px); }
  h1 { font-size: 50px; }
  .pill { padding: 0 14px; gap: 15px; }
}
@media (min-width: 601px) and (max-width: 900px) {
  .contact-scene { padding-top: 390px; }
  .portrait-stage { height: 470px; }
  .portrait-media { object-position: center 35%; }
  .portrait-shade { height: 490px; }
  .contact-content { padding-left: 40px; padding-right: 40px; }
  .intro-ghost { left: 56px; }
  .contact-header { padding: 0 40px; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
</style>
