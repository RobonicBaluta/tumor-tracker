// Auth state global: JWT en localStorage + user info + balance.

import { ref, computed } from 'vue'
import { API_BASE } from './useApi'

const TOKEN_KEY = 'zuruweb-jwt'

const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
const user = ref<{
  id: number
  discord_id: string
  username: string
  avatar: string | null
  riot_puuid: string | null
  riot_id: string | null
  currency: number
} | null>(null)

const isLoggedIn = computed(() => !!user.value)

function saveToken(t: string | null) {
  token.value = t
  if (t) localStorage.setItem(TOKEN_KEY, t)
  else localStorage.removeItem(TOKEN_KEY)
}

async function fetchMe() {
  if (!token.value) {
    user.value = null
    return
  }
  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token.value}` },
    })
    if (!res.ok) {
      saveToken(null)
      user.value = null
      return
    }
    user.value = await res.json()
  } catch {
    user.value = null
  }
}

function loginWithDiscord() {
  window.location.href = `${API_BASE}/auth/discord/login`
}

function logout() {
  saveToken(null)
  user.value = null
}

async function claimDaily() {
  if (!token.value) return null
  const res = await fetch(`${API_BASE}/currency/daily`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token.value}` },
  })
  if (!res.ok) return null
  const data = await res.json()
  if (user.value) user.value.currency = data.currency
  return data
}

async function refreshBalance() {
  if (!token.value) return
  try {
    const res = await fetch(`${API_BASE}/currency/balance`, {
      headers: { Authorization: `Bearer ${token.value}` },
    })
    if (!res.ok) return
    const data = await res.json()
    if (user.value) user.value.currency = data.currency
    return data
  } catch {}
}

async function linkRiot(gameName: string, tagLine: string) {
  if (!token.value) return null
  const res = await fetch(`${API_BASE}/auth/link-riot`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token.value}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ game_name: gameName, tag_line: tagLine }),
  })
  if (!res.ok) return null
  user.value = await res.json()
  return user.value
}

// Auto-detecta el ?token= en la URL al volver del callback de Discord
function handleAuthRedirect() {
  const url = new URL(window.location.href)
  const t = url.searchParams.get('token')
  if (t) {
    saveToken(t)
    url.searchParams.delete('token')
    window.history.replaceState({}, '', url.toString())
    fetchMe()
  } else if (token.value) {
    fetchMe()
  }
}

export function useAuth() {
  return {
    token,
    user,
    isLoggedIn,
    loginWithDiscord,
    logout,
    fetchMe,
    refreshBalance,
    claimDaily,
    linkRiot,
    handleAuthRedirect,
  }
}
