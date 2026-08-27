<script setup>
import { ref, onMounted } from 'vue'
import { useRecordsStore } from '../stores/records.js'

const store = useRecordsStore()
const title = ref('')
const filename = ref('')
const addMsg = ref('')

onMounted(() => {
  store.load()
})

function onAdd() {
  const res = store.addRecord({ title: title.value.trim(), filename: filename.value.trim() })
  if (!res.ok) {
    addMsg.value = res.msg
    return
  }
  addMsg.value = ''
  title.value = ''
  filename.value = ''
}

function onSearch(e) {
  store.setKeyword(e.target.value)
}
</script>

<template>
  <div>
    <h2>会议记录</h2>
    <div style="display: flex; gap: 8px; margin: 12px 0;">
      <input :value="store.keyword" placeholder="搜索标题或文件名" style="flex: 1;" @input="onSearch" />
      <button :disabled="store.loading" @click="store.load">刷新</button>
    </div>
    <p v-if="store.error" style="color: red;">{{ store.error }}</p>
    <p v-else-if="store.loading">加载中...</p>
    <p v-else>共 {{ store.records.length }} 条，已完成 {{ store.doneCount }} 条，筛选后 {{ store.filtered.length }} 条</p>

    <ul v-if="store.filtered.length">
      <li v-for="r in store.filtered" :key="r.id" style="margin: 6px 0;">
        <strong>{{ r.title || r.filename }}</strong>
        <span style="color: #888;"> — {{ r.filename }} — {{ r.status }}</span>
      </li>
    </ul>
    <p v-else-if="!store.loading">暂无记录</p>

    <div style="margin-top: 16px; border-top: 1px solid #eee; padding-top: 12px;">
      <h3>新增记录</h3>
      <div style="display: flex; gap: 8px; flex-wrap: wrap;">
        <input v-model="title" placeholder="标题" />
        <input v-model="filename" placeholder="文件名，如 meeting.wav" />
        <button @click="onAdd">添加</button>
      </div>
      <p v-if="addMsg" style="color: red;">{{ addMsg }}</p>
      <p style="color: #888; font-size: 12px;">提交后调用 records Store 的 addRecord，列表即时更新，无需刷新。</p>
    </div>
  </div>
</template>
