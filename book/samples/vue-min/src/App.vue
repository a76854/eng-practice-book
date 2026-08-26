<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface Task {
  id: string
  filename: string
  name?: string
  status: string
}

const tasks = ref<Task[]>([])
const loading = ref(true)
const error = ref('')
const keyword = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    // 优先尝试同源 mock（无后端也能展示），失败则回退内置 mock
    const res = await fetch('/mock.json')
    if (!res.ok) throw new Error(res.statusText)
    const data = (await res.json()) as { tasks: Task[] }
    tasks.value = data.tasks
  } catch (e: unknown) {
    // 回退：内置 mock 列表，保证离线/无后端也能渲染 <ul>
    const fallback: Task[] = [
      { id: '1', filename: 'meeting.wav', name: '周会', status: 'done' },
      { id: '2', filename: 'interview.mp3', status: 'processing' },
      { id: '3', filename: 'demo.wav', name: 'Demo 评审', status: 'pending' }
    ]
    // 仅当 fetch 失败才用 fallback；若错误可解析则显示 error
    if (tasks.value.length === 0) {
      tasks.value = fallback
      if (e instanceof Error && e.message) {
        // 保留静默回退，不强制显示 error；如需调试可取消下一行注释
        // error.value = e.message
      }
    }
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div style="max-width: 640px; margin: 40px auto; font-family: sans-serif; padding: 0 16px;">
    <h1>任务列表（vue-min）</h1>
    <div style="margin: 12px 0; display: flex; gap: 8px;">
      <input v-model="keyword" placeholder="搜索任务" style="flex: 1; padding: 6px 8px;" />
      <button :disabled="loading" @click="load">刷新</button>
    </div>
    <p v-if="error" style="color: red;">{{ error }}</p>
    <p v-else-if="loading">加载中...</p>
    <p v-else-if="!tasks.length">暂无任务</p>
    <ul v-else>
      <li v-for="t in tasks.filter(x => (x.name || x.filename).toLowerCase().includes(keyword.toLowerCase()))" :key="t.id">
        {{ t.name || t.filename }} — {{ t.status }}
      </li>
    </ul>
    <p style="margin-top: 16px; color: #888; font-size: 12px;">数据来源：fetch('/mock.json') 回退内置 mock；对应 MeetingToText 的 GET /api/tasks → v-for 渲染</p>
  </div>
</template>
