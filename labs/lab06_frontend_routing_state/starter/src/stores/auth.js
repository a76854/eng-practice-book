import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const LS_TOKEN = 'lab06_token'
const LS_USER = 'lab06_user'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(LS_TOKEN) || '')
  const user = ref(localStorage.getItem(LS_USER) || '')

  const isAuthed = computed(() => !!token.value)

  function login(username, password) {
    // 骨架阶段不校验后端，任意非空即可登录
    if (!username || !password) {
      return { ok: false, msg: '请输入用户名与密码' }
    }
    const t = `token-${Date.now()}`
    token.value = t
    user.value = username
    localStorage.setItem(LS_TOKEN, t)
    localStorage.setItem(LS_USER, username)
    return { ok: true }
  }

  function logout() {
    token.value = ''
    user.value = ''
    localStorage.removeItem(LS_TOKEN)
    localStorage.removeItem(LS_USER)
  }

  return { token, user, isAuthed, login, logout }
})
