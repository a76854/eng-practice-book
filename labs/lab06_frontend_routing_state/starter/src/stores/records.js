import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useRecordsStore = defineStore('records', () => {
  const records = ref([])
  const keyword = ref('')
  const loading = ref(false)
  const error = ref('')

  const filtered = computed(() => {
    const kw = keyword.value.trim().toLowerCase()
    if (!kw) return records.value
    return records.value.filter((r) => {
      const hay = `${r.title || ''} ${r.filename || ''}`.toLowerCase()
      return hay.includes(kw)
    })
  })

  const doneCount = computed(() => records.value.filter((r) => r.status === 'done').length)

  async function load() {
    loading.value = true
    error.value = ''
    try {
      const res = await fetch('/mock.json')
      if (!res.ok) throw new Error(res.statusText)
      const data = await res.json()
      // 兼容两种结构：{records} 或 {tasks}
      const list = data.records || data.tasks || []
      records.value = list.map((x) => ({
        id: String(x.id),
        title: x.title || x.name || '',
        filename: x.filename || '',
        status: x.status || 'pending'
      }))
    } catch (e) {
      // 回退到内置 mock，保证无后端也能演示
      if (records.value.length === 0) {
        records.value = [
          { id: '1', title: '周会', filename: 'meeting.wav', status: 'done' },
          { id: '2', title: '', filename: 'interview.mp3', status: 'processing' },
          { id: '3', title: 'Demo 评审', filename: 'demo.wav', status: 'pending' }
        ]
      }
      if (e instanceof Error && e.message) {
        // 静默回退，不强制展示错误，调试时可打开
        // error.value = e.message
      }
    } finally {
      loading.value = false
    }
  }

  function setKeyword(v) {
    keyword.value = v
  }

  function addRecord({ title, filename }) {
    if (!title && !filename) {
      return { ok: false, msg: '标题与文件名至少填一项' }
    }
    const rec = {
      id: String(Date.now()),
      title: title || '',
      filename: filename || '',
      status: 'pending'
    }
    records.value.unshift(rec)
    return { ok: true, record: rec }
  }

  return { records, keyword, loading, error, filtered, doneCount, load, setKeyword, addRecord }
})
