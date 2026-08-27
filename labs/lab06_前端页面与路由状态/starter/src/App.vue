<script setup>
import { useAuthStore } from './stores/auth.js'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()

function onLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div style="max-width: 760px; margin: 0 auto; font-family: sans-serif; padding: 16px;">
    <nav style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; padding-bottom: 12px;">
      <div style="display: flex; gap: 12px;">
        <router-link to="/records">会议记录</router-link>
        <router-link to="/login">登录</router-link>
      </div>
      <div style="display: flex; gap: 8px; align-items: center;">
        <span v-if="auth.isAuthed" style="color: #555;">{{ auth.user }}</span>
        <button v-if="auth.isAuthed" @click="onLogout">退出</button>
      </div>
    </nav>
    <main style="margin-top: 16px;">
      <router-view />
    </main>
    <p style="margin-top: 24px; color: #999; font-size: 12px;">
      Lab06 starter，Vue3 + Pinia + Vue Router。未登录访问 /records 会被守卫重定向到 /login。
    </p>
  </div>
</template>
