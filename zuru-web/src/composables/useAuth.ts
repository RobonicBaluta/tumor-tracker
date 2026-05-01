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

// Helpers para apuestas P2P
async function authedFetch(path: string, init?: RequestInit) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((init?.headers as Record<string, string>) || {}),
  }
  if (token.value) headers.Authorization = `Bearer ${token.value}`
  return fetch(`${API_BASE}${path}`, { ...init, headers })
}

async function createBet(matchId: string, gameId: number | undefined, side: 'blue' | 'red', amount: number) {
  const res = await authedFetch('/bets/create', {
    method: 'POST',
    body: JSON.stringify({ match_id: matchId, game_id: gameId, side, amount }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Error')
  await refreshBalance()
  return data
}

async function acceptBet(shareCode: string) {
  const res = await authedFetch(`/bets/${shareCode}/accept`, { method: 'POST' })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Error')
  await refreshBalance()
  return data
}

async function cancelBet(shareCode: string) {
  const res = await authedFetch(`/bets/${shareCode}/cancel`, { method: 'POST' })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Error')
  await refreshBalance()
  return data
}

async function fetchBet(shareCode: string) {
  const res = await fetch(`${API_BASE}/bets/${shareCode}`)
  if (!res.ok) return null
  return await res.json()
}

async function fetchMyBets() {
  if (!token.value) return []
  const res = await authedFetch('/bets/mine')
  if (!res.ok) return []
  return await res.json()
}

async function fetchOpenBets() {
  const res = await fetch(`${API_BASE}/bets/open`)
  if (!res.ok) return []
  return await res.json()
}

async function fetchLeaderboard(kind: 'currency' | 'bets' | 'accuracy') {
  const res = await fetch(`${API_BASE}/leaderboards/${kind}`)
  if (!res.ok) return []
  return await res.json()
}

async function fetchFriends() {
  if (!token.value) return []
  const res = await authedFetch('/friends')
  if (!res.ok) return []
  return await res.json()
}

async function addFriend(riotId: string) {
  const res = await authedFetch('/friends/add', {
    method: 'POST',
    body: JSON.stringify({ riot_id: riotId }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Error')
  return data
}

async function acceptFriend(friendshipId: number) {
  await authedFetch(`/friends/${friendshipId}/accept`, { method: 'POST' })
}

async function rejectFriend(friendshipId: number) {
  await authedFetch(`/friends/${friendshipId}/reject`, { method: 'POST' })
}

async function fetchNotifications() {
  if (!token.value) return []
  const res = await authedFetch('/notifications')
  if (!res.ok) return []
  return await res.json()
}

async function markNotificationsRead(ids: number[] | null = null) {
  if (!token.value) return
  await authedFetch('/notifications/read', {
    method: 'POST',
    body: JSON.stringify({ ids }),
  })
}

async function createRoom(name: string) {
  const res = await authedFetch('/rooms/create', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Error')
  return data
}

async function joinRoom(code: string, riotId?: string) {
  const res = await authedFetch(`/rooms/${code}/join`, {
    method: 'POST',
    body: JSON.stringify({ riot_id: riotId || '' }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Error')
  return data
}

async function leaveRoom(code: string, riotId: string) {
  const res = await authedFetch(`/rooms/${code}/leave`, {
    method: 'POST',
    body: JSON.stringify({ riot_id: riotId }),
  })
  return res.ok
}

async function fetchRoom(code: string) {
  const res = await fetch(`${API_BASE}/rooms/${code}`)
  if (!res.ok) return null
  return await res.json()
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
    createBet,
    acceptBet,
    cancelBet,
    fetchBet,
    fetchMyBets,
    fetchOpenBets,
    fetchLeaderboard,
    fetchFriends,
    addFriend,
    acceptFriend,
    rejectFriend,
    fetchNotifications,
    markNotificationsRead,
    createRoom,
    joinRoom,
    leaveRoom,
    fetchRoom,
  }
}
