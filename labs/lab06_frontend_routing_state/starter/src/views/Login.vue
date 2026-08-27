<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const auth = useAuthStore()
const router = useRouter()
const username = ref('')
const password = ref('')
const msg = ref('')

function onLogin() {
  const res = auth.login(username.value.trim(), password.value)
  if (!res.ok) {
    msg.value = res.msg
    return
  }
  msg.value = ''
  router.push('/records')
}
</script>

<template>
  <div>
    <h2>登录</h2>
    <p style="color: #888;">骨架阶段任意非空用户名与密码即可登录，登录态写入 localStorage。</p>
    <div style="display: flex; flex-direction: column; gap: 8px; max-width: 320px;">
      <input v-model="username" placeholder="用户名" />
      <input v-model="password" type="password" placeholder="密码" />
      <button @click="onLogin">登录</button>
      <p v-if="msg" style="color: red;">{{ msg }}</p>
      <p v-if="auth.isAuthed" style="color: green;">已登录为 {{ auth.user }}</p>
    </div>
  </div>
</template>
