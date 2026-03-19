<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';

const canvasRef = ref<HTMLCanvasElement | null>(null);
let animationId: number;

onMounted(() => {
  const canvas = canvasRef.value;
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  // 设置画布尺寸
  const resize = () => {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  };
  resize();
  window.addEventListener('resize', resize);

  // 配置
  const fontSize = 14;
  const columns = Math.floor(canvas.width / fontSize) + 5;

  // 每列的状态
  interface Drop {
    y: number;
    speed: number;
    length: number;
    chars: string[];
    lastUpdate: number;
    updateInterval: number;
  }

  const drops: Drop[] = [];

  // 初始化列
  for (let i = 0; i < columns; i++) {
    const length = 3 + Math.floor(Math.random() * 35);
    const chars: string[] = [];
    for (let j = 0; j < length; j++) {
      chars.push(Math.floor(Math.random() * 10).toString());
    }

    drops.push({
      y: -Math.random() * canvas.height * 2,
      speed: 0.3 + Math.random() * 0.6,
      length,
      chars,
      lastUpdate: 0,
      updateInterval: 50 + Math.random() * 100
    });
  }

  // 颜色缓存（更暗更低调，增加红色）
  const colors = {
    head: ['#44aa44', '#44aaaa', '#4444aa', '#aa4444'],
    body: ['#008844', '#0066aa', '#004488', '#880022']
  };

  let frameCount = 0;

  const draw = (timestamp: number) => {
    frameCount++;

    // 半透明覆盖层创建拖尾效果
    ctx.fillStyle = 'rgba(10, 10, 10, 0.08)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.font = `${fontSize}px 'JetBrains Mono', monospace`;
    ctx.textAlign = 'center';

    for (let i = 0; i < drops.length; i++) {
      const drop = drops[i];
      const x = i * fontSize + fontSize / 2;

      // 更新字符（控制频率）
      if (timestamp - drop.lastUpdate > drop.updateInterval) {
        for (let j = 0; j < drop.length; j++) {
          // 头部字符变化更频繁
          if (j === drop.length - 1 || Math.random() < 0.1) {
            drop.chars[j] = Math.floor(Math.random() * 10).toString();
          }
        }
        drop.lastUpdate = timestamp;
      }

      // 绘制每个字符
      for (let j = 0; j < drop.length; j++) {
        const charY = drop.y - (drop.length - 1 - j) * fontSize;

        if (charY < -fontSize || charY > canvas.height + fontSize) continue;

        const isHead = j === drop.length - 1;
        const fadeIndex = j / drop.length;

        // 颜色动画
        const colorPhase = (timestamp / 1000 + i * 0.1) % 4;
        let color: string;

        if (isHead) {
          const headIndex = Math.floor(colorPhase);
          color = colors.head[headIndex];
          ctx.shadowBlur = 8;
          ctx.shadowColor = color;
        } else {
          const bodyIndex = Math.floor(colorPhase);
          color = colors.body[bodyIndex];
          ctx.shadowBlur = 0;
        }

        // 透明度渐变（整体更暗）
        const alpha = isHead ? 0.4 : 0.08 + fadeIndex * 0.12;
        ctx.fillStyle = color;
        ctx.globalAlpha = alpha;
        ctx.fillText(drop.chars[j], x, charY);
      }

      ctx.globalAlpha = 1;
      ctx.shadowBlur = 0;

      // 更新位置
      drop.y += drop.speed;

      // 重置
      if (drop.y - drop.length * fontSize > canvas.height) {
        drop.y = -Math.random() * 200;
        drop.speed = 0.3 + Math.random() * 0.6;
        drop.length = 3 + Math.floor(Math.random() * 35);
      }
    }

    animationId = requestAnimationFrame(draw);
  };

  animationId = requestAnimationFrame(draw);

  onUnmounted(() => {
    cancelAnimationFrame(animationId);
    window.removeEventListener('resize', resize);
  });
});
</script>

<template>
  <canvas ref="canvasRef" class="matrix-canvas" aria-hidden="true"></canvas>
</template>

<style scoped>
.matrix-canvas {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}
</style>
