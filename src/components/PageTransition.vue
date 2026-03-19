<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';

const props = defineProps<{
  show: boolean;
  progress: number;
}>();

const canvasRef = ref<HTMLCanvasElement | null>(null);
let ctx: CanvasRenderingContext2D | null = null;
let frameCount = 0;

// 粒子系统
interface Particle {
  x: number;
  y: number;
  char: string;
  alpha: number;
  speed: number;
  size: number;
}

let particles: Particle[] = [];
let scanlineOffset = 0;

// 初始化粒子
const initParticles = (w: number, h: number) => {
  particles = [];
  // 数字粒子
  for (let i = 0; i < 80; i++) {
    particles.push({
      x: Math.random() * w,
      y: Math.random() * h,
      char: Math.floor(Math.random() * 10).toString(),
      alpha: 0.1 + Math.random() * 0.3,
      speed: 0.5 + Math.random() * 1.5,
      size: 10 + Math.random() * 8
    });
  }
};

// 三阶段动画配置 - 时间由 App.vue 控制
// 淡出 300ms，淡入 300ms，扫描分段随机 1900-2900ms，总时间 2.5-3.5秒
const FADE_OUT_RATIO = 300 / 3000;  // 约 0.1
const FADE_IN_RATIO = 300 / 3000;   // 约 0.1
const SCAN_START = FADE_OUT_RATIO;
const SCAN_END = 1 - FADE_IN_RATIO;

// 绘制老电视扫描线效果
const drawScanlines = (ctx: CanvasRenderingContext2D, w: number, h: number) => {
  ctx.fillStyle = 'rgba(0, 0, 0, 0.1)';
  for (let y = scanlineOffset; y < h; y += 4) {
    ctx.fillRect(0, y, w, 1);
  }
  scanlineOffset = (scanlineOffset + 0.5) % 4;
};

// 绘制老电视噪点
const drawNoise = (ctx: CanvasRenderingContext2D, w: number, h: number, intensity: number) => {
  const imageData = ctx.getImageData(0, 0, w, h);
  const data = imageData.data;

  for (let i = 0; i < data.length; i += 16) { // 每隔4个像素处理一个，优化性能
    if (Math.random() < intensity) {
      const noise = Math.random() * 30;
      data[i] = Math.min(255, data[i] + noise);     // R
      data[i + 1] = Math.min(255, data[i + 1] + noise); // G
      data[i + 2] = Math.min(255, data[i + 2] + noise); // B
    }
  }

  ctx.putImageData(imageData, 0, 0);
};

// 绘制CRT屏幕弯曲效果
const drawCRTCurvature = (ctx: CanvasRenderingContext2D, w: number, h: number) => {
  const gradient = ctx.createRadialGradient(w/2, h/2, h/3, w/2, h/2, h);
  gradient.addColorStop(0, 'transparent');
  gradient.addColorStop(0.7, 'rgba(0,0,0,0.1)');
  gradient.addColorStop(1, 'rgba(0,0,0,0.3)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, w, h);
};

// 绘制过渡动画
const drawTransition = (progress: number) => {
  if (!ctx || !canvasRef.value) return;

  const w = canvasRef.value.width;
  const h = canvasRef.value.height;
  frameCount++;

  // 清除画布为纯黑
  ctx.fillStyle = '#0a0a0a';
  ctx.fillRect(0, 0, w, h);

  // 计算当前阶段和归一化进度
  let phase: 'FADE_OUT' | 'SCAN' | 'FADE_IN';
  let phaseProgress: number;

  if (progress < SCAN_START) {
    phase = 'FADE_OUT';
    phaseProgress = progress / SCAN_START;
  } else if (progress < SCAN_END) {
    phase = 'SCAN';
    phaseProgress = (progress - SCAN_START) / (SCAN_END - SCAN_START);
  } else {
    phase = 'FADE_IN';
    phaseProgress = (progress - SCAN_END) / (1 - SCAN_END);
  }

  // 缓动函数
  const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);
  const easeInOutCubic = (t: number) =>
    t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

  const easedProgress = phase === 'SCAN'
    ? easeInOutCubic(phaseProgress)
    : easeOutCubic(phaseProgress);

  // 计算统一的遮罩透明度
  // 目标是：屏幕缓缓变黑 -> 保持黑屏（扫描）-> 由黑转亮
  let screenAlpha = 0;

  if (phase === 'FADE_OUT') {
    // 淡出阶段：0 -> 1（透明到纯黑）
    screenAlpha = easedProgress;
  } else if (phase === 'SCAN') {
    // 扫描阶段：保持纯黑，但扫描元素从100%淡出到0%
    screenAlpha = 1;
  } else {
    // 淡入阶段：1 -> 0（纯黑到透明）
    screenAlpha = 1 - easedProgress;
  }

  // ===== 阶段1&2：淡出和扫描阶段 =====
  if (phase === 'FADE_OUT' || phase === 'SCAN') {
    // 绘制黑色遮罩
    const gradient = ctx.createLinearGradient(0, 0, 0, h);
    gradient.addColorStop(0, `rgba(10, 10, 10, ${screenAlpha * 0.85})`);
    gradient.addColorStop(0.5, `rgba(10, 10, 10, ${screenAlpha * 0.95})`);
    gradient.addColorStop(1, `rgba(10, 10, 10, ${screenAlpha * 0.85})`);

    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, w, h);

    // 噪点
    if (screenAlpha > 0.05) {
      drawNoise(ctx, w, h, 0.03 * screenAlpha);
    }
  }

  // ===== 扫描效果（仅在扫描阶段显示，带整体淡出）=====
  if (phase === 'SCAN') {
    // 扫描元素在扫描阶段后期整体淡出
    // 前70%保持清晰，后30%逐渐淡出
    let scanElementsAlpha = 1;
    if (easedProgress > 0.7) {
      scanElementsAlpha = 1 - (easedProgress - 0.7) / 0.3;
      scanElementsAlpha = Math.max(0, scanElementsAlpha);
    }

    // 扫描线位置
    const scanY = h * easedProgress;

    // 扫描线光效
    const scanGradient = ctx.createLinearGradient(0, scanY - 150, 0, scanY + 150);
    scanGradient.addColorStop(0, 'transparent');
    scanGradient.addColorStop(0.45, `rgba(183, 255, 59, ${0.15 * scanElementsAlpha})`);
    scanGradient.addColorStop(0.5, `rgba(183, 255, 59, ${0.8 * scanElementsAlpha})`);
    scanGradient.addColorStop(0.55, `rgba(183, 255, 59, ${0.15 * scanElementsAlpha})`);
    scanGradient.addColorStop(1, 'transparent');

    ctx.fillStyle = scanGradient;
    ctx.fillRect(0, scanY - 150, w, 300);

    // 核心扫描线
    ctx.fillStyle = `rgba(200, 255, 150, ${scanElementsAlpha})`;
    ctx.shadowBlur = 20 * scanElementsAlpha;
    ctx.shadowColor = '#b7ff3b';
    ctx.fillRect(0, scanY - 1, w, 2);
    ctx.shadowBlur = 0;

    // 数字拖尾
    ctx.font = '14px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';

    const trailLength = 30;
    for (let i = 0; i < trailLength; i++) {
      const trailY = scanY - 20 - i * 8;
      if (trailY < 0) break;

      const trailAlpha = (1 - i / trailLength) * 0.4 * scanElementsAlpha;
      if (trailAlpha <= 0) continue;

      // 数字拖尾更居中，减小波动幅度
      const x = w / 2 + Math.sin(i * 0.2 + frameCount * 0.03) * 20;
      ctx.fillStyle = `rgba(183, 255, 59, ${trailAlpha})`;
      const digit = (frameCount + i) % 10;
      ctx.fillText(digit.toString(), x, trailY);
    }

    // 已扫描区域的数字矩阵
    if (scanY > 100 && scanElementsAlpha > 0) {
      ctx.font = '12px "JetBrains Mono", monospace';
      const cols = Math.floor(w / 40);
      const rows = Math.floor((scanY - 50) / 30);

      for (let c = 0; c < cols; c++) {
        for (let r = 0; r < rows; r += 2) {
          const seed = c * 1000 + r + Math.floor(frameCount / 10);
          const pseudoRandom = (seed * 9301 + 49297) % 233280 / 233280;
          if (pseudoRandom > 0.4) continue;

          const x = c * 40 + 20;
          const y = r * 30 + 25;
          const age = (scanY - y) / h;
          const fadeOut = Math.max(0, 1 - age * 2);

          if (fadeOut > 0) {
            const digit = Math.floor(pseudoRandom * 10);
            const alpha = fadeOut * 0.25 * scanElementsAlpha;
            ctx.fillStyle = `rgba(0, 136, 68, ${alpha})`;
            ctx.fillText(digit.toString(), x, y);
          }
        }
      }
    }

    // 扫描线附近的漂浮数字粒子
    if (scanElementsAlpha > 0) {
      for (let i = 0; i < 15; i++) {
        const angle = (frameCount * 0.02 + i / 15) * Math.PI * 2;
        const radius = 20 + i * 5;
        const px = w / 2 + Math.cos(angle) * radius * 2;
        const py = scanY + Math.sin(angle * 2) * 30;

        if (px > 0 && px < w && py > 0 && py < h) {
          const distFromScan = Math.abs(py - scanY);
          const alpha = Math.max(0, 1 - distFromScan / 60) * 0.6 * scanElementsAlpha;

          if (alpha > 0) {
            ctx.fillStyle = `rgba(183, 255, 59, ${alpha})`;
            ctx.shadowBlur = 8 * scanElementsAlpha;
            ctx.shadowColor = '#b7ff3b';
            const digit = (i + frameCount) % 10;
            ctx.font = `bold ${12 + i}px "JetBrains Mono", monospace`;
            ctx.fillText(digit.toString(), px, py);
            ctx.shadowBlur = 0;
          }
        }
      }
    }
  }

  // ===== 阶段3：淡入阶段（仅绘制遮罩，无任何扫描元素）=====
  if (phase === 'FADE_IN') {
    // 渐变遮罩：从纯黑逐渐淡出显示内容
    const gradient = ctx.createLinearGradient(0, 0, 0, h);
    gradient.addColorStop(0, `rgba(10, 10, 10, ${screenAlpha * 0.85})`);
    gradient.addColorStop(0.5, `rgba(10, 10, 10, ${screenAlpha * 0.95})`);
    gradient.addColorStop(1, `rgba(10, 10, 10, ${screenAlpha * 0.85})`);

    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, w, h);

    // 淡入阶段只有轻微噪点，无任何绿色元素
    if (screenAlpha > 0.05) {
      drawNoise(ctx, w, h, 0.02 * screenAlpha);
    }
  }

  // ===== 老电视效果层（仅扫描阶段显示）=====
  if (phase === 'SCAN') {
    // 扫描元素整体淡出因子
    let scanElementsAlpha = 1;
    if (easedProgress > 0.7) {
      scanElementsAlpha = 1 - (easedProgress - 0.7) / 0.3;
      scanElementsAlpha = Math.max(0, scanElementsAlpha);
    }

    // 扫描线
    drawScanlines(ctx, w, h);

    // CRT屏幕弯曲效果
    drawCRTCurvature(ctx, w, h);

    // 偶尔的水平扫描线干扰（80%之后不再显示）
    if (easedProgress < 0.8 && Math.random() > 0.7) {
      const glitchY = Math.random() * h;
      ctx.fillStyle = `rgba(183, 255, 59, ${0.1 * scanElementsAlpha})`;
      ctx.fillRect(0, glitchY, w, 2);
    }

    // ===== 全局漂浮数字粒子（仅扫描阶段）=====
    ctx.font = '12px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';

    particles.forEach((p, i) => {
      // 更新粒子位置
      p.y += p.speed;
      if (p.y > h) {
        p.y = -20;
        p.x = Math.random() * w;
      }

      // 粒子透明度：基础透明度 * 扫描淡出因子
      let particleAlpha = p.alpha * scanElementsAlpha;

      // 靠近扫描线的粒子更亮
      const scanY = h * easedProgress;
      const distFromScan = Math.abs(p.y - scanY);
      if (distFromScan < 100) {
        particleAlpha *= 1.5;
      }

      // 闪烁效果
      const flicker = 0.7 + Math.sin(frameCount * 0.1 + i) * 0.3;
      particleAlpha *= flicker;

      if (particleAlpha > 0.05) {
        ctx.fillStyle = `rgba(0, 136, 68, ${particleAlpha})`;
        ctx.fillText(p.char, p.x, p.y);
      }
    });
  }

  // ===== 中央进度显示 =====
  if (phase === 'SCAN') {
    // 进度显示在扫描后期淡出，避免切换到淡入阶段时闪烁
    let textOpacity = 1;
    if (easedProgress > 0.75) {
      textOpacity = 1 - (easedProgress - 0.75) / 0.25;
    }
    textOpacity = Math.max(0, textOpacity);

    if (textOpacity > 0.01) {
      ctx.font = 'bold 20px "JetBrains Mono", monospace';
      ctx.textAlign = 'center';

      // 文字发光效果随透明度淡出
      ctx.shadowBlur = 15 * textOpacity;
      ctx.shadowColor = '#b7ff3b';

      // 固定的进度文字（无随机解码，避免闪烁）
      const displayText = easedProgress < 0.5 ? 'LOADING' : 'COMPLETE';
      ctx.fillStyle = `rgba(183, 255, 59, ${textOpacity})`;
      ctx.fillText(`[ ${displayText} ]`, w / 2, h / 2);

      // 进度条
      const barWidth = 200;
      const barHeight = 3;
      const barX = (w - barWidth) / 2;
      const barY = h / 2 + 40;

      // 背景条
      ctx.shadowBlur = 0;
      ctx.fillStyle = `rgba(183, 255, 59, ${0.15 * textOpacity})`;
      ctx.fillRect(barX, barY, barWidth, barHeight);

      // 进度条（带发光）
      ctx.fillStyle = `rgba(183, 255, 59, ${textOpacity})`;
      ctx.shadowBlur = 8 * textOpacity;
      ctx.shadowColor = '#b7ff3b';
      ctx.fillRect(barX, barY, barWidth * easedProgress, barHeight);
      ctx.shadowBlur = 0;

      // 百分比
      ctx.font = '14px "JetBrains Mono", monospace';
      ctx.fillStyle = `rgba(183, 255, 59, ${textOpacity})`;
      ctx.fillText(`${Math.floor(easedProgress * 100)}%`, w / 2, barY + 25);
    }
  }

  // 确保清除所有发光效果（防止扫描线残留）
  ctx.shadowBlur = 0;

  // 最后的轻微暗角效果（仅在扫描阶段显示，避免淡入时闪烁）
  if (phase === 'SCAN') {
    // 扫描元素整体淡出因子
    let scanElementsAlpha = 1;
    if (easedProgress > 0.7) {
      scanElementsAlpha = 1 - (easedProgress - 0.7) / 0.3;
      scanElementsAlpha = Math.max(0, scanElementsAlpha);
    }

    const vignette = ctx.createRadialGradient(w/2, h/2, h/2.5, w/2, h/2, h);
    vignette.addColorStop(0, 'transparent');
    vignette.addColorStop(1, `rgba(0,0,0,${0.2 * scanElementsAlpha})`);
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, w, h);
  }
};

onMounted(() => {
  const canvas = canvasRef.value;
  if (!canvas) return;

  ctx = canvas.getContext('2d');
  if (!ctx) return;

  const resize = () => {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    initParticles(canvas.width, canvas.height);
  };
  resize();
  window.addEventListener('resize', resize);

  // 初始绘制
  drawTransition(props.progress);
});

// 监听进度变化
watch(() => props.progress, (newProgress) => {
  drawTransition(newProgress);
});
</script>

<template>
  <div class="page-transition">
    <canvas ref="canvasRef" class="transition-canvas"></canvas>
  </div>
</template>

<style scoped>
.page-transition {
  position: fixed;
  inset: 0;
  z-index: 9999;
  pointer-events: all;
}

.transition-canvas {
  width: 100%;
  height: 100%;
  image-rendering: pixelated;
}
</style>
