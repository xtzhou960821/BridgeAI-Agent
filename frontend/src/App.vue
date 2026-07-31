<script setup lang="ts">
const tasks = [
  {
    id: 'task_001',
    title: '桥梁无人机影像质量检查',
    status: 'V0.2 示例任务',
    artifactCount: 1,
  },
]
</script>

<template>
  <main class="shell">
    <section class="hero">
      <p class="eyebrow">BridgeAI-Agent V0.2</p>
      <h1>桥梁与道路巡检 AI Agent 工作台</h1>
      <p>
        当前版本用于验证工程骨架：任务列表、任务详情、人工复核和报告区将在后续迭代逐步接入真实 API。
      </p>
    </section>

    <section class="panel" aria-labelledby="task-list-title">
      <h2 id="task-list-title">任务列表</h2>
      <article v-for="task in tasks" :key="task.id" class="task-card">
        <div>
          <h3>{{ task.title }}</h3>
          <p>{{ task.id }} · {{ task.artifactCount }} 个 Artifact</p>
        </div>
        <span>{{ task.status }}</span>
      </article>
    </section>

    <section class="panel" aria-labelledby="task-detail-title">
      <h2 id="task-detail-title">任务详情占位</h2>
      <p>后续将接入 Workflow 事件流、Tool 调用记录、病害清单、证据图和人工复核结果。</p>
    </section>
  </main>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  box-sizing: border-box;
  padding: 48px;
  color: #17201a;
  background:
    radial-gradient(circle at top left, rgba(52, 99, 77, 0.16), transparent 28rem),
    linear-gradient(135deg, #f7f4ec 0%, #eef3ec 100%);
  font-family:
    Inter, "PingFang SC", "Microsoft YaHei", system-ui, -apple-system, BlinkMacSystemFont,
    sans-serif;
}

.hero,
.panel {
  max-width: 960px;
  margin: 0 auto 24px;
  padding: 28px;
  border: 1px solid rgba(23, 32, 26, 0.1);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 24px 60px rgba(23, 32, 26, 0.08);
}

.eyebrow {
  margin: 0 0 8px;
  color: #52715f;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

h1,
h2,
h3,
p {
  margin-top: 0;
}

h1 {
  font-size: clamp(2rem, 5vw, 4rem);
  line-height: 1.05;
}

.task-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 18px;
  border-radius: 18px;
  background: #f7faf5;
}

.task-card span {
  padding: 6px 10px;
  border-radius: 999px;
  color: #315b45;
  background: #ddebe1;
  font-size: 0.85rem;
  white-space: nowrap;
}
</style>
