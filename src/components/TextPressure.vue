<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

// Vue adaptation of the supplied React Bits / Juan Fuentes TextPressure example.
const props = withDefaults(defineProps<{ text?: string; active?: boolean }>(), {
  text: "Let's talk.",
  active: true,
});
const characters = computed(() => Array.from(props.text));
const container = ref<HTMLElement | null>(null);
const title = ref<HTMLElement | null>(null);
const maximumSize = ref<HTMLElement | null>(null);
const radius = 0.5;
const smoothing = 0.5;
const idleSpeed = 1;
const wavePeriod = 3.2;
const rippleLife = 1300;
const staticAxes = "'wght' 500, 'wdth' 100, 'slnt' 0";
type Point = { x: number; y: number };
type Ripple = Point & { start: number };
const pointer = { x: 0, y: 0, seen: false };
const mouse: Point = { x: 0, y: 0 };
let letters: HTMLElement[] = [];
let applied: string[] = [];
let ripples: Ripple[] = [];
let frame = 0;
let last = 0;
let clock = 0;
let engage = 0;
let visible = false;
let fontReady = false;
let disposed = false;
let motionQuery: MediaQueryList | undefined;
let intersectionObserver: IntersectionObserver | undefined;
let resizeObserver: ResizeObserver | undefined;

const distance = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y);
const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

function canAnimate() {
  return !disposed && props.active && visible && fontReady && !document.hidden && !motionQuery?.matches;
}

function stop() {
  cancelAnimationFrame(frame);
  frame = 0;
  last = 0;
}

function resetLetters() {
  letters.forEach(letter => { letter.style.fontVariationSettings = staticAxes; });
  applied = [];
  ripples = [];
  pointer.seen = false;
  engage = 0;
}

function wake() {
  if (!frame && canAnimate()) frame = requestAnimationFrame(tick);
}

function updateActivity() {
  if (canAnimate()) wake();
  else {
    stop();
    pointer.seen = false;
    ripples = [];
    if (motionQuery?.matches || !fontReady) resetLetters();
  }
}

function fitTitle() {
  if (!container.value || !maximumSize.value || !title.value) return;
  // Measure the widest supported axes, including slant overhang. The line keeps
  // its original font size and height; only narrow containers need an x-scale.
  const available = container.value.getBoundingClientRect().width;
  const widest = maximumSize.value.getBoundingClientRect().width;
  title.value.style.transform = `scaleX(${Math.min(1, available / Math.max(widest, 1))})`;
  wake();
}

function ripplePressure(point: Point, now: number, span: number) {
  const band = Math.max(span * 0.14, 32);
  let total = 0;
  for (const ripple of ripples) {
    const age = (now - ripple.start) / 1000;
    if (age <= 0 || age >= rippleLife / 1000) continue;
    const offset = (distance(ripple, point) - age * span * 1.25) / band;
    if (Math.abs(offset) >= 1) continue;
    const fade = 1 - age / (rippleLife / 1000);
    const swell = (1 - offset * offset) ** 2 * fade * fade * Math.min(1, age / 0.06);
    total = 1 - (1 - total) * (1 - swell);
  }
  return total;
}

function tick(now: number) {
  frame = 0;
  if (!canAnimate() || !title.value) { last = 0; return; }
  const elapsed = last ? Math.min(now - last, 64) : 1000 / 60;
  last = now;
  const follow = 1 - Math.exp(-elapsed / (1000 * smoothing * smoothing));
  mouse.x += (pointer.x - mouse.x) * follow;
  mouse.y += (pointer.y - mouse.y) * follow;

  // Batch layout reads before changing any letter's axes.
  const box = title.value.getBoundingClientRect();
  const centers = letters.map(letter => {
    const rect = letter.getBoundingClientRect();
    return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
  });
  const inside = pointer.seen && pointer.x >= box.left && pointer.x <= box.right
    && pointer.y >= box.top && pointer.y <= box.bottom;
  const present = inside ? 1 : 0;
  engage += (present - engage) * (1 - Math.exp(-elapsed / 320));
  if (Math.abs(present - engage) < 0.002) engage = present;
  const idling = engage < 1;
  if (idling) clock += elapsed / 1000 * idleSpeed;
  ripples = ripples.filter(ripple => now - ripple.start < rippleLife);
  const span = Math.max(box.width, 1);
  const reach = Math.max(span * radius, 1);
  const spread = Math.max(radius * 2, 0.2);
  let changed = false;

  centers.forEach((center, index) => {
    let pressure = clamp01(1 - distance(mouse, center) / reach);
    if (idling) {
      const position = (center.x - box.left) / span;
      const crest = 0.5 + 0.5 * Math.cos(Math.PI * 2 * (position / spread - clock / wavePeriod));
      const resting = crest * crest;
      pressure = resting + (pressure - resting) * engage;
    }
    if (ripples.length) pressure = 1 - (1 - pressure) * (1 - ripplePressure(center, now, span));
    // Roboto Flex has slnt, not ital. Avoid its extreme compression so this
    // mixed-case heading stays readable at the trough of the idle wave.
    const settings = `'wght' ${Math.round(250 + 700 * pressure)}, 'wdth' ${(80 + 55 * pressure).toFixed(2)}, 'slnt' ${(-10 * pressure).toFixed(2)}`;
    if (applied[index] !== settings) {
      letters[index]!.style.fontVariationSettings = settings;
      applied[index] = settings;
      changed = true;
    }
  });

  const moving = distance(mouse, pointer) > 0.1;
  if (idling || moving || engage !== present || ripples.length || changed) wake();
  else last = 0;
}

function trackPointer(event: PointerEvent) {
  if (!canAnimate() || !event.isPrimary) return;
  pointer.x = event.clientX;
  pointer.y = event.clientY;
  if (!pointer.seen) { mouse.x = pointer.x; mouse.y = pointer.y; }
  pointer.seen = true;
  wake();
}

function releasePointer(event?: Event) {
  if (event?.type === 'pointerup' && (event as PointerEvent).pointerType === 'mouse') return;
  pointer.seen = false;
  wake();
}

function press(event: PointerEvent) {
  if (!canAnimate() || !event.isPrimary || event.button !== 0) return;
  trackPointer(event);
  ripples.push({ x: event.clientX, y: event.clientY, start: performance.now() });
  if (ripples.length > 6) ripples.shift();
  wake();
}

function onMotionChange() {
  resetLetters();
  updateActivity();
}

watch(() => props.active, updateActivity);
watch(() => props.text, () => {
  letters = Array.from(title.value?.querySelectorAll<HTMLElement>('.text-pressure__char') ?? []);
  resetLetters();
  fitTitle();
}, { flush: 'post' });

onMounted(() => {
  letters = Array.from(title.value?.querySelectorAll<HTMLElement>('.text-pressure__char') ?? []);
  motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  motionQuery.addEventListener('change', onMotionChange);
  document.addEventListener('visibilitychange', updateActivity);
  window.addEventListener('pointermove', trackPointer, { passive: true });
  window.addEventListener('pointerup', releasePointer, { passive: true });
  window.addEventListener('pointercancel', releasePointer, { passive: true });
  window.addEventListener('blur', releasePointer);
  window.addEventListener('scroll', wake, { passive: true, capture: true });
  document.documentElement.addEventListener('pointerleave', releasePointer);
  container.value?.addEventListener('pointerdown', press, { passive: true });

  intersectionObserver = new IntersectionObserver(([entry]) => {
    visible = Boolean(entry?.isIntersecting);
    updateActivity();
  });
  if (container.value) intersectionObserver.observe(container.value);
  resizeObserver = new ResizeObserver(fitTitle);
  if (container.value) resizeObserver.observe(container.value);
  if (maximumSize.value) resizeObserver.observe(maximumSize.value);
  fitTitle();

  // A failed local font leaves readable, static fallback text instead of a
  // continuous animation loop with no visible effect.
  document.fonts.load('500 16px "Contact Roboto Flex"', props.text).then(faces => {
    if (disposed) return;
    fontReady = faces.length > 0;
    fitTitle();
    updateActivity();
  }).catch(() => {
    if (!disposed) { fontReady = false; updateActivity(); }
  });
});

onBeforeUnmount(() => {
  disposed = true;
  stop();
  ripples = [];
  intersectionObserver?.disconnect();
  resizeObserver?.disconnect();
  motionQuery?.removeEventListener('change', onMotionChange);
  document.removeEventListener('visibilitychange', updateActivity);
  window.removeEventListener('pointermove', trackPointer);
  window.removeEventListener('pointerup', releasePointer);
  window.removeEventListener('pointercancel', releasePointer);
  window.removeEventListener('blur', releasePointer);
  window.removeEventListener('scroll', wake, { capture: true });
  document.documentElement.removeEventListener('pointerleave', releasePointer);
  container.value?.removeEventListener('pointerdown', press);
});
</script>

<template>
  <span ref="container" class="text-pressure" aria-hidden="true">
    <span ref="maximumSize" class="text-pressure__measure" aria-hidden="true">{{ text }}</span>
    <span ref="title" class="text-pressure__text">
      <span v-for="(character, index) in characters" :key="index" class="text-pressure__char" aria-hidden="true"
        :class="{ 'text-pressure__accent': character === '.' && index === characters.length - 1 }">{{ character }}</span>
    </span>
  </span>
</template>

<style scoped>
@font-face {
  font-family: 'Contact Roboto Flex';
  src: url('../assets/fonts/RobotoFlex-Latin.woff2') format('woff2');
  font-style: normal;
  font-weight: 100 1000;
  font-stretch: 25% 151%;
  font-display: swap;
}
.text-pressure {
  position: relative;
  display: block;
  width: 100%;
  height: 1.07em;
  font-family: 'Contact Roboto Flex', 'Inter', 'Arial', sans-serif;
  font-kerning: none;
  font-variant-ligatures: none;
  font-synthesis: none;
  letter-spacing: -.035em;
  white-space: pre;
  touch-action: pan-y;
}
.text-pressure__text { display: inline-flex; transform-origin: left center; }
.text-pressure__char { display: inline-block; font-variation-settings: 'wght' 500, 'wdth' 100, 'slnt' 0; }
.text-pressure__accent { color: #b7ff3b; }
.text-pressure__measure {
  position: absolute;
  top: 0;
  left: 0;
  visibility: hidden;
  pointer-events: none;
  padding-right: .12em;
  font-variation-settings: 'wght' 950, 'wdth' 135, 'slnt' -10;
}
@media (prefers-reduced-motion: reduce) {
  .text-pressure__char { font-variation-settings: 'wght' 500, 'wdth' 100, 'slnt' 0 !important; }
}
</style>
