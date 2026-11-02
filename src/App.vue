<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import HomeMenu from './components/Home_Menu.vue';
import MatrixRain from './components/MatrixRain.vue';
import PageTransition from './components/PageTransition.vue';
import ContactPortrait from './components/ContactPortrait.vue';
import ResumeAssistant from './components/ResumeAssistant.vue';

type Page = 'home' | 'resume' | 'contact';
const pageFromHash = (): Page => {
  const hash = window.location.hash.slice(1);
  return hash === 'contact' || hash === 'resume' ? hash : 'home';
};
const initialPage = pageFromHash();
const heroVisible = ref(false);
const showContact = ref(initialPage === 'contact');
// Keep one prepared portrait instead of fetching and decoding on every visit.
const contactPrepared = ref(initialPage === 'contact');
let prepareTimer: ReturnType<typeof setTimeout> | undefined;
const showResume = ref(initialPage === 'resume');
const showTransition = ref(false);
const transitionProgress = ref(0);
const isRiaHovered = ref(false);
let transitionFrame = 0;
let switchTimer: ReturnType<typeof setTimeout> | undefined;
let finishTimer: ReturnType<typeof setTimeout> | undefined;

const cancelTransition = () => {
  cancelAnimationFrame(transitionFrame);
  clearTimeout(switchTimer);
  clearTimeout(finishTimer);
  showTransition.value = false;
};

const setPage = (page: Page) => {
  if (page === 'contact') contactPrepared.value = true;
  showContact.value = page === 'contact';
  showResume.value = page === 'resume';
};

const randomDuration = (min: number, max: number) =>
  Math.floor(Math.random() * (max - min + 1)) + min;

const playTransition = (callback: () => void) => {
  cancelTransition();
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    callback();
    return;
  }
  showTransition.value = true;
  transitionProgress.value = 0;
  const scanSegments = [randomDuration(250, 400), randomDuration(300, 500), randomDuration(300, 600), randomDuration(250, 400)];
  const totalDuration = 600 + scanSegments.reduce((sum, segment) => sum + segment, 0);
  const startTime = performance.now();
  const animate = (currentTime: number) => {
    transitionProgress.value = Math.min((currentTime - startTime) / totalDuration, 1);
    if (transitionProgress.value < 1) transitionFrame = requestAnimationFrame(animate);
    else finishTimer = setTimeout(() => { showTransition.value = false; }, 100);
  };
  switchTimer = setTimeout(callback, 300 + scanSegments[0] + scanSegments[1] + scanSegments[2] * 0.6);
  transitionFrame = requestAnimationFrame(animate);
};

const navigate = (page: Page) => {
  if (window.location.hash !== `#${page}`) window.history.pushState(null, '', `#${page}`);
  // Early clicks can prepare media during the original transition too.
  if (page === 'contact') contactPrepared.value = true;
  playTransition(() => setPage(page));
};
const goToContact = () => navigate('contact');
const goToResume = () => navigate('resume');
const goBack = () => navigate('home');
const syncFromHash = () => {
  cancelTransition();
  setPage(pageFromHash());
};

onMounted(() => {
  heroVisible.value = true;
  // Let the initial page paint before preparing the contact media in the background.
  prepareTimer = setTimeout(() => { contactPrepared.value = true; }, 1200);
  window.addEventListener('hashchange', syncFromHash);
});
onUnmounted(() => {
  clearTimeout(prepareTimer);
  cancelTransition();
  window.removeEventListener('hashchange', syncFromHash);
});
</script>

<template>
  <div class="page" :class="{ 'page--contact': showContact }">
    <PageTransition
      v-if="showTransition"
      :show="showTransition"
      :progress="transitionProgress"
    />

    <HomeMenu
      v-if="!showContact"
      :active-section="showContact ? 'contact' : (showResume ? 'resume' : 'home')"
      :on-light="showContact"
      @go-home="goBack" 
      @go-contact="goToContact"
      @go-resume="goToResume"
    />

    <MatrixRain v-if="!showContact" />

    <div v-if="!showContact" class="decorations" aria-hidden="true">
      <div class="deco-square deco-1"></div>
      <div class="deco-square deco-2"></div>
      <div class="deco-square deco-3"></div>
      <div class="deco-square deco-4"></div>
      <div class="deco-square deco-5"></div>
      <div class="deco-dot deco-dot-1"></div>
      <div class="deco-dot deco-dot-2"></div>
    </div>

    <div v-if="!showContact" class="bg-grid" aria-hidden="true">
      <div class="grid-line" v-for="i in 20" :key="i"></div>
    </div>

    <div v-if="!showContact" class="logo-container" :class="{ 'logo-visible': heroVisible }">
      <div class="logo-icon">
        <span class="logo-letter">R</span>
      </div>
      <span class="logo-name">RIA</span>
    </div>

    <div v-if="!showContact && !showResume" class="hero" :class="{ 'hero-visible': heroVisible }">
      <div class="hero-line hero-line--top" aria-label="HI,">
        <span
          v-for="(char, i) in ['H', 'I', ',']"
          :key="i"
          class="hero-letter cursor-target text-white"
          :style="{ animationDelay: `${i * 0.08}s` }"
        >{{ char }}</span>
      </div>

      <div class="hero-line hero-line--bottom" aria-label="HERE IS RIA">
        <span
          v-for="(char, i) in ['H', 'E', 'R', 'E', '\u00A0', 'I', 'S', '\u00A0']"
          :key="i"
          class="hero-letter cursor-target text-white"
          :style="{ animationDelay: `${0.3 + i * 0.06}s` }"
        >{{ char }}</span>
        <span
          class="ria-group cursor-target"
          @mouseenter="isRiaHovered = true"
          @mouseleave="isRiaHovered = false"
          :class="{ 'ria-hovered': isRiaHovered }"
        >
          <span
            v-for="(char, i) in ['R', 'I', 'A']"
            :key="i"
            class="hero-letter ria-letter"
            :class="'text-lime'"
            :style="{ animationDelay: `${0.3 + (8 + i) * 0.06}s` }"
          >{{ char }}</span>
        </span>
      </div>

      <div class="subtitle" :class="{ 'subtitle-visible': isRiaHovered }">
        <p class="subtitle-tags">极客 · 产品 · 项目思维</p>
        <p class="subtitle-text">你好~这里是石耳，也叫RIA</p>
      </div>

      <div class="cta-group">
        <button class="cta-btn cursor-target" @click="goToResume">
          <span>关于我</span>
          <svg class="arrow-right" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M5 12h14M12 5l7 7-7 7"/>
          </svg>
        </button>
        
        <button class="cta-btn cta-btn-outline cursor-target" @click="goToContact">
          <span>联系我</span>
          <svg class="arrow-down" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 5v14M19 12l-7 7-7-7"/>
          </svg>
        </button>
      </div>
    </div>

    <div v-else-if="showResume" class="resume-page" :class="{ 'resume-visible': showResume }">
      <div class="resume-container">
        <div class="resume-header">
          <h2 class="resume-title">关于我</h2>
          <p class="resume-subtitle">About Me</p>
        </div>
        
        <div class="resume-content">
          <div class="resume-section">
            <h3 class="section-title">个人简介</h3>
            <p class="section-text">
              你好，我是陈科瑾（Ria）。<br>
              具备 <strong>AI 大模型应用</strong> 与 <strong>全栈开发</strong> 能力的 <strong>AI 产品经理</strong>。<br>
              <br>
              致力于将前沿的 AI 技术（Transformers, LangChain, RAG）转化为实际落地的商业价值。
              拥有扎实的工程底座，融合 <strong>Java (Spring Boot)</strong> 与 <strong>Python</strong> 双栈技术，
              结合 <strong>Docker/K8s</strong> 容器化部署经验，构建高效、可扩展的智能化解决方案。<br>
              <br>
              热衷于探索 <strong>Multi-Agent</strong> 协作与 <strong>GraphRAG</strong> 知识图谱增强生成技术，
              推动产品从 0 到 1 的创新与迭代。
            </p>
          </div>

          <div class="resume-grid">
            <div class="resume-card">
              <h4 class="card-title">AI 技术栈</h4>
              <ul class="skill-list">
                <li>LangChain / Dify</li>
                <li>RAG / GraphRAG</li>
                <li>LoRA / QLoRA / PEFT</li>
                <li>vLLM / DeepSpeed</li>
                <li>PyTorch / Transformers</li>
                <li>Prompt Engineering</li>
              </ul>
            </div>
            
            <div class="resume-card">
              <h4 class="card-title">工程技术栈</h4>
              <ul class="skill-list">
                <li>Java / Spring Boot</li>
                <li>Python / FastAPI</li>
                <li>Vue.js / TypeScript</li>
                <li>Docker / K8s</li>
                <li>MySQL / Redis / Milvus</li>
              </ul>
            </div>
          </div>

          <div class="resume-section">
            <h3 class="section-title">工作经历</h3>
            <div class="timeline">
              <div class="timeline-item">
                <div class="timeline-dot"></div>
                <div class="timeline-content">
                  <h4 class="timeline-role">AI 产品经理 @ 顺丰速运</h4>
                  <p class="timeline-desc">
                    负责「丰晓易」智能助手 Agent 化升级与核心场景落地。<br>
                    • 覆盖账单触达、差异查因、调账、发票服务、支付核销 <strong>5 类月结结算场景</strong>，完成需求优先级、业务规则与验收口径定义<br>
                    • 参与治理 <strong>500+ 份业务文档</strong>、沉淀 <strong>150+ 对标准 QA</strong>，完成 6 类 RAG 知识域与 7 类只读 API Tools 的能力映射<br>
                    • 参与建立分层评测与版本迭代机制，推动意图识别准确率 <strong>93%+</strong>、RAG 召回率 <strong>96%+</strong>
                  </p>
                </div>
              </div>

              <div class="timeline-item">
                <div class="timeline-dot"></div>
                <div class="timeline-content">
                  <h4 class="timeline-role">AI 应用开发 / AI 产品经理 @ 浙大网新</h4>
                  <p class="timeline-desc">
                    参与企业级数据与 AI 中台、智能外呼系统建设。<br>
                    • 负责「大先生」Corpus 语料库与文件管理模块后端开发，参与模型训练与部署链路维护<br>
                    • 参与政企业务材料智能审核应用原型：基于 <strong>Dify</strong> 串联材料解析、字段抽取、规则校验与人工复核
                  </p>
                </div>
              </div>

              <div class="timeline-item">
                <div class="timeline-dot"></div>
                <div class="timeline-content">
                  <h4 class="timeline-role">AI 工程师 @ 智谱华章</h4>
                  <p class="timeline-desc">
                    核心参与 <strong>Critic（思维链评判模型）</strong>项目研发，负责训练数据建设与标注团队协同。<br>
                    • 设计并构建高质量 <strong>Chain of Thought (CoT)</strong> 训练数据集，通过 <strong>Step-by-Step</strong> 推理路径增强模型在复杂数学与代码任务中的表现<br>
                    • 参与 <strong>Process Reward Model (PRM)</strong> 的训练与验证，优化 <strong>RLHF (PPO)</strong> 算法中的奖励机制，使模型具备细粒度逻辑验证与 <strong>Self-Correction（自我修正）</strong>能力<br>
                    • 制定 <strong>Span 任务标注规则</strong>，完成 4 批共 <strong>48,000 条</strong>训练样本的清洗与质量复核；培训并协同 <strong>20+ 名</strong>线上实习生，累计交付 <strong>100,000+ 条</strong>标注数据，返修率从 30% 降至 <strong>12%</strong>
                  </p>
                </div>
              </div>
            </div>
          </div>
          <ResumeAssistant />
        </div>
      </div>
    </div>

    <ContactPortrait v-if="contactPrepared" v-show="showContact" :active="showContact"
      @go-home="goBack" @go-resume="goToResume" />

    <div v-if="!showContact && !showResume" class="scroll-hint" aria-hidden="true">
      <span class="scroll-text">SCROLL</span>
      <div class="scroll-line"></div>
    </div>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #0a0a0a;
  color: #ffffff;
  position: relative;
  overflow: hidden;
  font-family: 'Inter', 'SF Pro Display', system-ui, -apple-system, sans-serif;
  cursor: none;
}

.page--contact {
  background: #171916;
  cursor: auto;
}

.bg-grid {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 1;
  opacity: 0.03;
  display: flex;
  justify-content: space-between;
  padding: 0 5%;
}

.grid-line {
  width: 1px;
  height: 100%;
  background: linear-gradient(to bottom, transparent, #b7ff3b, transparent);
}

.decorations {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 2;
}

.deco-square {
  position: absolute;
  width: 12px;
  height: 12px;
  background: #b7ff3b;
  transform: rotate(45deg);
}

.deco-1 {
  top: 25%;
  left: 8%;
  animation: float 6s ease-in-out infinite;
}

.deco-2 {
  top: 20%;
  right: 15%;
  width: 8px;
  height: 8px;
  animation: float 8s ease-in-out infinite 1s;
}

.deco-3 {
  bottom: 35%;
  left: 12%;
  width: 10px;
  height: 10px;
  animation: float 7s ease-in-out infinite 0.5s;
}

.deco-4 {
  top: 40%;
  right: 8%;
  width: 6px;
  height: 6px;
  animation: float 9s ease-in-out infinite 2s;
}

.deco-5 {
  bottom: 25%;
  right: 20%;
  animation: float 5s ease-in-out infinite 1.5s;
}

.deco-dot {
  position: absolute;
  width: 4px;
  height: 4px;
  background: #b7ff3b;
  border-radius: 50%;
}

.deco-dot-1 {
  top: 30%;
  right: 25%;
  animation: pulse 3s ease-in-out infinite;
}

.deco-dot-2 {
  bottom: 40%;
  left: 20%;
  animation: pulse 4s ease-in-out infinite 1s;
}

@keyframes float {
  0%, 100% { transform: translateY(0) rotate(45deg); }
  50% { transform: translateY(-20px) rotate(45deg); }
}

@keyframes pulse {
  0%, 100% { opacity: 0.3; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.5); }
}

.logo-container {
  position: fixed;
  top: 32px;
  left: 40px;
  display: flex;
  align-items: center;
  gap: 12px;
  z-index: 100;
  opacity: 0;
  transform: translateY(-20px);
  transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}

.logo-visible {
  opacity: 1;
  transform: translateY(0);
}

.logo-icon {
  width: 40px;
  height: 40px;
  background: #b7ff3b;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-letter {
  font-size: 22px;
  font-weight: 900;
  color: #0a0a0a;
}

.logo-name {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #ffffff;
}

.hero {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  width: 100%;
  z-index: 10;
  padding: 0 20px;
  pointer-events: none;
}

.hero > * {
  pointer-events: auto;
}

.hero-line {
  margin: 0;
  font-weight: 900;
  line-height: 0.95;
  letter-spacing: 0.05em;
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
}

.hero-line--top {
  font-size: clamp(56px, 10vw, 140px);
  margin-bottom: 0.05em;
}

.hero-line--bottom {
  font-size: clamp(48px, 9vw, 120px);
}

.hero-letter {
  display: inline-block;
  opacity: 0;
  transform: translateY(30px);
  animation: letterIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  will-change: transform, opacity;
}

.hero-visible .hero-letter {
  animation-play-state: running;
}

@keyframes letterIn {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.text-white {
  color: #ffffff;
  text-shadow:
    1px 1px 0 rgba(255,255,255,0.1),
    2px 2px 0 rgba(0,0,0,0.3),
    3px 3px 0 rgba(0,0,0,0.2),
    4px 4px 0 rgba(0,0,0,0.1),
    0 0 40px rgba(255,255,255,0.1);
}

.hero-line {
  filter: drop-shadow(0 4px 20px rgba(0,0,0,0.4));
}

.text-white {
  color: #ffffff;
  text-shadow:
    1px 1px 0 rgba(255,255,255,0.15),
    2px 2px 0 rgba(0,0,0,0.3),
    3px 3px 0 rgba(0,0,0,0.2),
    4px 4px 0 rgba(0,0,0,0.1),
    0 0 30px rgba(255,255,255,0.08),
    0 10px 30px rgba(0,0,0,0.3);
}

.text-lime {
  color: #b7ff3b;
  text-shadow:
    1px 1px 0 #8bc31a,
    2px 2px 0 #6fa314,
    3px 3px 0 #5a850f,
    4px 4px 0 #45680b,
    5px 5px 0 #304a08,
    6px 6px 0 #1a2d04,
    8px 8px 20px rgba(0,0,0,0.5),
    0 0 60px rgba(183,255,59,0.3),
    0 0 100px rgba(183,255,59,0.1);
}

.ria-group {
  display: inline-flex;
  cursor: none;
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.ria-group:hover,
.ria-hovered {
  transform: scale(1.05);
}

.ria-letter {
  display: inline-block;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.ria-group:hover .ria-letter,
.ria-hovered .ria-letter {
  text-shadow:
    1px 1px 0 #8bc31a,
    2px 2px 0 #6fa314,
    3px 3px 0 #5a850f,
    4px 4px 0 #45680b,
    5px 5px 0 #304a08,
    6px 6px 0 #1a2d04,
    8px 8px 20px rgba(0,0,0,0.5),
    0 0 80px rgba(183,255,59,0.5),
    0 0 120px rgba(183,255,59,0.3);
}

.subtitle {
  margin-top: 3rem;
  opacity: 0;
  transform: translateY(20px);
  transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
  pointer-events: none;
}

.subtitle-visible {
  opacity: 1;
  transform: translateY(0);
}

.subtitle-tags {
  font-size: 0.9rem;
  color: #b7ff3b;
  letter-spacing: 0.3em;
  font-weight: 600;
  text-shadow:
    0 0 10px rgba(183, 255, 59, 0.4),
    0 0 20px rgba(183, 255, 59, 0.2);
}

.subtitle-text {
  font-size: 1rem;
  color: rgba(255, 255, 255, 0.7);
  margin-top: 0.6rem;
  font-weight: 400;
  letter-spacing: 0.15em;
}

.subtitle-text::before {
  content: '>';
  color: #b7ff3b;
  margin-right: 0.5rem;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.cta-group {
  margin-top: 2.5rem;
  display: flex;
  gap: 1.5rem;
  justify-content: center;
  opacity: 0;
  animation: fadeInUp 0.8s ease-out 1.4s forwards;
}

.cta-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.8rem 2rem;
  background: #b7ff3b;
  border: 1px solid #b7ff3b;
  border-radius: 50px;
  color: #0a0a0a;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: none;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
  overflow: hidden;
}

.cta-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: #ffffff;
  transform: scaleX(0);
  transform-origin: right;
  transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  z-index: 1;
  opacity: 0.2;
}

.cta-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 30px rgba(183,255,59,0.3);
}

.cta-btn:hover::before {
  transform: scaleX(1);
  transform-origin: left;
}

.cta-btn-outline {
  background: transparent;
  color: #ffffff;
  border: 1px solid rgba(255,255,255,0.3);
}

.cta-btn-outline:hover {
  border-color: #b7ff3b;
  color: #b7ff3b;
  background: rgba(183,255,59,0.1);
}

.arrow-right, .arrow-down {
  width: 16px;
  height: 16px;
  transition: transform 0.3s ease;
}

.cta-btn:hover .arrow-right {
  transform: translateX(3px);
}

.cta-btn:hover .arrow-down {
  transform: translateY(3px);
}

.resume-page {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 20;
  overflow-y: auto;
  padding: 80px 20px 40px;
  opacity: 0;
  animation: aboutIn 0.5s ease-out forwards;
  scrollbar-width: none;
}

.resume-page::-webkit-scrollbar {
  display: none;
}

.resume-container {
  max-width: 900px;
  margin: 0 auto;
  padding-bottom: 60px;
}

.resume-header {
  text-align: center;
  margin-bottom: 3rem;
}

.resume-title {
  font-size: 2.5rem;
  font-weight: 900;
  color: #ffffff;
  letter-spacing: 0.1em;
  margin-bottom: 0.5rem;
  text-shadow: 0 0 20px rgba(183, 255, 59, 0.3);
}

.resume-subtitle {
  font-size: 1rem;
  color: #b7ff3b;
  letter-spacing: 0.2em;
  text-transform: uppercase;
}

.resume-content {
  display: flex;
  flex-direction: column;
  gap: 3rem;
}

.resume-section {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 20px;
  padding: 2rem;
  backdrop-filter: blur(10px);
  transition: all 0.3s ease;
}

.resume-section:hover {
  border-color: rgba(183, 255, 59, 0.3);
  background: rgba(255, 255, 255, 0.05);
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

.section-title {
  font-size: 1.2rem;
  color: #b7ff3b;
  margin-bottom: 1.5rem;
  display: flex;
  align-items: center;
  gap: 10px;
}

.section-title::before {
  content: '';
  width: 4px;
  height: 20px;
  background: #b7ff3b;
  border-radius: 2px;
}

.section-text {
  font-size: 1rem;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.8);
}

.resume-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 2rem;
}

.resume-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 20px;
  padding: 2rem;
  transition: all 0.3s ease;
}

.resume-card:hover {
  transform: translateY(-5px);
  border-color: rgba(183, 255, 59, 0.3);
}

.card-title {
  font-size: 1.1rem;
  color: #ffffff;
  margin-bottom: 1.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding-bottom: 0.8rem;
}

.skill-list {
  list-style: none;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.skill-list li {
  background: rgba(183, 255, 59, 0.1);
  color: #b7ff3b;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 0.9rem;
  border: 1px solid rgba(183, 255, 59, 0.2);
}

.timeline {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  position: relative;
  padding-left: 20px;
}

.timeline::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 2px;
  background: rgba(255, 255, 255, 0.1);
}

.timeline-item {
  position: relative;
}

.timeline-dot {
  position: absolute;
  left: -24px;
  top: 6px;
  width: 10px;
  height: 10px;
  background: #b7ff3b;
  border-radius: 50%;
  box-shadow: 0 0 10px rgba(183, 255, 59, 0.5);
}

.timeline-date {
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.5);
  display: block;
  margin-bottom: 0.3rem;
}

.timeline-role {
  font-size: 1.1rem;
  color: #ffffff;
  margin-bottom: 0.5rem;
}

.timeline-desc {
  font-size: 0.95rem;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.6;
}

.about-page {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 100px 40px 40px;
  background: #f6f7fb;
  opacity: 0;
  animation: aboutIn 0.5s ease-out forwards;
}

@keyframes aboutIn {
  to {
    opacity: 1;
  }
}

.about-content {
  position: relative;
  z-index: 2;
  text-align: center;
  max-width: 500px;
  padding: 1.5rem 1.25rem;
  border-radius: 28px;
}

.avatar-container {
  position: relative;
  display: inline-block;
  margin-bottom: 2rem;
}

.avatar-wrapper {
  width: 150px;
  height: 150px;
  border-radius: 50%;
  border: 3px solid #b7ff3b;
  overflow: hidden;
  position: relative;
  z-index: 2;
}

.avatar {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: 50% 35%;
}

.avatar-glow {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 170px;
  height: 170px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(183,255,59,0.3) 0%, transparent 70%);
  animation: avatarPulse 3s ease-in-out infinite;
  z-index: 1;
}

@keyframes avatarPulse {
  0%, 100% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 0.6;
  }
  50% {
    transform: translate(-50%, -50%) scale(1.1);
    opacity: 0.3;
  }
}

.about-title {
  font-size: 2.5rem;
  font-weight: 900;
  margin-top: 2.5rem;
  margin-bottom: 1.5rem;
  color: #ffffff;
  letter-spacing: 0.1em;
  text-shadow:
    -1px -1px 0 #808080,
    -2px -2px 0 #606060,
    -3px -3px 0 #404040,
    0 0 20px rgba(255, 255, 255, 0.3),
    0 0 40px rgba(255, 255, 255, 0.1),
    0 0 60px rgba(183, 255, 59, 0.2);
}

.about-name {
  font-size: 1.8rem;
  font-weight: 700;
  color: #ffffff;
  margin-bottom: 0.5rem;
}

.about-role {
  font-size: 1rem;
  color: #b7ff3b;
  letter-spacing: 0.15em;
  margin-bottom: 1.5rem;
}

.about-divider {
  width: 60px;
  height: 2px;
  background: linear-gradient(90deg, transparent, #b7ff3b, transparent);
  margin: 0 auto 1.5rem;
}

.about-desc {
  font-size: 1rem;
  color: rgba(255,255,255,0.7);
  line-height: 1.8;
  max-width: 400px;
  margin-left: auto;
  margin-right: auto;
}

.contact-section {
  margin-top: 2rem;
}

.contact-title {
  font-size: 0.85rem;
  color: rgba(255,255,255,0.5);
  letter-spacing: 0.2em;
  margin-bottom: 1rem;
  text-transform: uppercase;
}

.contact-links {
  display: flex;
  justify-content: center;
  gap: 1.5rem;
}

.contact-link {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 16px;
  color: rgba(255,255,255,0.7);
  text-decoration: none;
  min-width: 80px;
  cursor: none;
  transition: all 0.3s ease;
  position: relative;
}

.contact-link:hover {
  background: rgba(183,255,59,0.1);
  border-color: #b7ff3b;
  color: #b7ff3b;
  transform: translateY(-3px);
}

.contact-link::after {
  content: attr(data-tooltip);
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%) translateY(10px);
  background: rgba(10, 10, 10, 0.9);
  border: 1px solid #b7ff3b;
  color: #b7ff3b;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 0.8rem;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  box-shadow: 0 4px 20px rgba(0,0,0,0.5);
  z-index: 100;
  margin-bottom: 12px;
}

.contact-link:hover::after {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}

.toast-notification {
  position: fixed;
  top: 100px;
  left: 50%;
  transform: translateX(-50%) translateY(-20px);
  background: rgba(10, 10, 10, 0.95);
  border: 1px solid #b7ff3b;
  color: #b7ff3b;
  padding: 12px 24px;
  border-radius: 50px;
  font-size: 0.9rem;
  font-weight: 500;
  opacity: 0;
  pointer-events: none;
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  z-index: 1000;
  box-shadow: 0 0 20px rgba(183, 255, 59, 0.2);
  display: flex;
  align-items: center;
  gap: 8px;
  backdrop-filter: blur(10px);
}

.toast-notification::before {
  content: '✓';
  font-weight: bold;
}

.toast-visible {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}

.contact-link svg {
  width: 24px;
  height: 24px;
}

.contact-link span {
  font-size: 0.75rem;
  letter-spacing: 0.05em;
}

.scroll-hint {
  position: absolute;
  bottom: 40px;
  left: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  opacity: 0;
  animation: fadeIn 0.8s ease-out 1.8s forwards;
  z-index: 10;
}

.scroll-text {
  font-size: 0.65rem;
  letter-spacing: 0.2em;
  color: rgba(255,255,255,0.4);
  writing-mode: vertical-rl;
  text-orientation: mixed;
}

.scroll-line {
  width: 1px;
  height: 60px;
  background: linear-gradient(to bottom, rgba(183,255,59,0.8), transparent);
  animation: scrollLine 2s ease-in-out infinite;
}

@keyframes scrollLine {
  0%, 100% { transform: scaleY(0); transform-origin: top; }
  50% { transform: scaleY(1); transform-origin: top; }
  51% { transform-origin: bottom; }
  100% { transform: scaleY(0); transform-origin: bottom; }
}

@keyframes fadeIn {
  to { opacity: 1; }
}

@media (max-width: 768px) {
  .logo-container {
    left: 20px;
    top: 24px;
  }

  .hero-line--top {
    font-size: clamp(48px, 14vw, 100px);
  }

  .hero-line--bottom {
    font-size: clamp(36px, 10vw, 80px);
  }

  .scroll-hint {
    left: 20px;
    bottom: 20px;
  }

  .subtitle {
    margin-top: 2rem;
  }

  .back-btn {
    top: 90px;
    left: 20px;
  }

  .about-page {
    padding: 90px 20px 40px;
  }

  .avatar-wrapper {
    width: 120px;
    height: 120px;
  }

  .avatar-glow {
    width: 140px;
    height: 140px;
  }

  .about-title {
    font-size: 2rem;
  }

  .about-name {
    font-size: 1.5rem;
  }

  .contact-links {
    gap: 1rem;
  }

  .contact-link {
    min-width: 70px;
    padding: 0.8rem;
  }
}

.page--contact .logo-name,
.page--contact .about-name,
.page--contact .about-title,
.page--contact .about-desc {
  color: #1a1a1a;
  text-shadow: none;
}

.page--contact .about-role {
  color: #4d7c0f;
  text-shadow: none;
}

.page--contact .contact-link {
  background: rgba(255, 255, 255, 0.72);
  border-color: rgba(20, 20, 20, 0.14);
  color: #222;
}

.page--contact .contact-link:hover {
  background: #fff;
  border-color: #1a1a1a;
  color: #1a1a1a;
}
</style>
