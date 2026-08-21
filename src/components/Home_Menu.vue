<script setup lang="ts">
import TargetCursor from './TargetCursor.vue';

const props = defineProps<{
  activeSection?: 'home' | 'resume' | 'projects' | 'contact'
}>();

const emit = defineEmits<{
  goHome: []
  goResume: []
  goContact: []
}>();

const handleHomeClick = () => {
  emit('goHome');
};

const handleResumeClick = () => {
  emit('goResume');
};

const handleContactClick = () => {
  emit('goContact');
};
</script>

<template>
  <div class="home-menu">
    <TargetCursor
      :spin-duration="2"
      :hide-default-cursor="true"
    />

    <nav class="nav">
      <ul class="nav-list">
        <li><a class="nav-link cursor-target" :class="{ 'nav-link--active': activeSection === 'home' }" href="#home" @click.prevent="handleHomeClick">首页</a></li>
        <li><a class="nav-link cursor-target" :class="{ 'nav-link--active': activeSection === 'resume' }" href="#resume" @click.prevent="handleResumeClick">关于我</a></li>
        <li><a class="nav-link cursor-target" :class="{ 'nav-link--active': activeSection === 'contact' }" href="#contact" @click.prevent="handleContactClick">联系我</a></li>
      </ul>
    </nav>
  </div>
</template>

<style scoped>
.home-menu {
  position: relative;
}

.nav {
  position: fixed;
  top: 24px;
  right: 32px;
  z-index: 1000;
}

.nav-list {
  display: flex;
  align-items: center;
  gap: 20px;
  list-style: none;
  margin: 0;
  padding: 0;
}

.nav-link {
  display: inline-block;
  padding: 8px 4px;
  color: #f5f5f7;
  font-size: 18px;
  font-weight: 600;
  text-decoration: none;
  letter-spacing: 0.02em;
  cursor: none;
}

.nav-link:hover,
.nav-link--active {
  text-decoration: underline;
  text-underline-offset: 6px;
}

.nav-link--active {
  color: #76ff7a;
  text-shadow:
    0 0 6px rgba(118, 255, 122, 0.7),
    0 0 18px rgba(118, 255, 122, 0.45),
    0 0 32px rgba(118, 255, 122, 0.35);
  animation: neonPulse 1.6s ease-in-out infinite;
}

@keyframes neonPulse {
  0%,
  100% {
    text-shadow:
      0 0 6px rgba(118, 255, 122, 0.7),
      0 0 18px rgba(118, 255, 122, 0.45),
      0 0 32px rgba(118, 255, 122, 0.35);
  }
  50% {
    text-shadow:
      0 0 10px rgba(118, 255, 122, 0.9),
      0 0 28px rgba(118, 255, 122, 0.6),
      0 0 44px rgba(118, 255, 122, 0.45);
  }
}
</style>
