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
  can_claim_daily?: boolean
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
  if (user.value) {
    user.value.currency = data.currency
    user.value.can_claim_daily = false
  }
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

async function createBet(matchId: string, gameId: number | undefined, side: 'blue' | 'red', amount: number, isHouse = false) {
  const res = await authedFetch('/bets/create', {
    method: 'POST',
    body: JSON.stringify({ match_id: matchId, game_id: gameId, side, amount, is_house: isHouse }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Error')
  await refreshBalance()
  return data
}

// One-click "este jugador será sus" — house bet con multiplicador por tier
async function placePlayerBet(matchId: string, targetPuuid: string, targetName: string, amount: number) {
  const res = await authedFetch('/bets/player', {
    method: 'POST',
    body: JSON.stringify({ match_id: matchId, target_puuid: targetPuuid, target_name: targetName, amount }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Error')
  await refreshBalance()
  return data
}

async function createStatBet(opts: {
  matchId: string
  gameId?: number
  side: 'over' | 'under'
  amount: number
  targetPuuid: string
  targetName: string
  statType: 'kills' | 'deaths' | 'assists' | 'kda'
  threshold: number
}) {
  const res = await authedFetch('/bets/create', {
    method: 'POST',
    body: JSON.stringify({
      match_id: opts.matchId,
      game_id: opts.gameId,
      side: opts.side,
      amount: opts.amount,
      bet_kind: 'stat',
      target_puuid: opts.targetPuuid,
      target_name: opts.targetName,
      stat_type: opts.statType,
      threshold: opts.threshold,
    }),
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

// Escanea bets matched del user y resuelve las que correspondan a matches
// terminados. Idempotente. Devuelve {checked, resolved, refunded}.
async function resolveMyPendingBets() {
  if (!token.value) return null
  const res = await authedFetch('/bets/resolve-mine', { method: 'POST' })
  if (!res.ok) return null
  const data = await res.json()
  if (data.resolved > 0 || data.refunded > 0) await refreshBalance()
  return data
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

async function fetchClusters(k = 4) {
  const res = await fetch(`${API_BASE}/analytics/clusters?k=${k}`)
  if (!res.ok) return { clusters: [], n: 0, k }
  return await res.json()
}

async function fetchDeathHeatmap(gameName: string, tagLine: string, count = 10, queue = 420) {
  const params = new URLSearchParams({
    game_name: gameName, tag_line: tagLine,
    count: String(count), queue: String(queue),
  })
  const res = await fetch(`${API_BASE}/analytics/death-heatmap?${params}`)
  if (!res.ok) return null
  return await res.json()
}

async function previewMultiplier(matchId: string, side: 'blue' | 'red') {
  const res = await fetch(`${API_BASE}/bets/preview-multiplier?match_id=${encodeURIComponent(matchId)}&side=${side}`)
  if (!res.ok) return null
  return await res.json() as { multiplier: number; is_underdog: boolean; underdog_bonus: number }
}

// 1v1 Challenges
async function createChallenge(opts: {
  statType: 'kills' | 'deaths' | 'assists' | 'kda' | 'cs' | 'gold' | 'damage' | 'tumor_score'
  amount: number
  comparison?: 'higher_wins' | 'lower_wins'
  format?: 'single' | 'bo3' | 'bo5' | 'bo10'
}) {
  const res = await authedFetch('/challenges/create', {
    method: 'POST',
    body: JSON.stringify({
      stat_type: opts.statType,
      amount: opts.amount,
      comparison: opts.comparison,
      format: opts.format || 'single',
    }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Error')
  await refreshBalance()
  return data
}

// Room bets (item #4)
async function createRoomBet(roomCode: string, stake: number, ttlHours = 24) {
  const res = await authedFetch(`/rooms/${roomCode}/bets/create`, {
    method: 'POST',
    body: JSON.stringify({ stake, ttl_hours: ttlHours }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Error')
  await refreshBalance()
  return data
}

async function joinRoomBet(roomCode: string, rbid: number) {
  const res = await authedFetch(`/rooms/${roomCode}/bets/${rbid}/join`, { method: 'POST' })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Error')
  await refreshBalance()
  return data
}

async function startRoomBet(roomCode: string, rbid: number) {
  const res = await authedFetch(`/rooms/${roomCode}/bets/${rbid}/start`, { method: 'POST' })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Error')
  return data
}

async function cancelRoomBet(roomCode: string, rbid: number) {
  const res = await authedFetch(`/rooms/${roomCode}/bets/${rbid}/cancel`, { method: 'POST' })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Error')
  await refreshBalance()
  return data
}

async function fetchRoomBets(roomCode: string) {
  const res = await fetch(`${API_BASE}/rooms/${roomCode}/bets`)
  if (!res.ok) return []
  return await res.json()
}

async function acceptChallenge(shareCode: string) {
  const res = await authedFetch(`/challenges/${shareCode}/accept`, { method: 'POST' })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Error')
  await refreshBalance()
  return data
}

async function cancelChallenge(shareCode: string) {
  const res = await authedFetch(`/challenges/${shareCode}/cancel`, { method: 'POST' })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Error')
  await refreshBalance()
  return data
}

async function submitChallengeMatch(shareCode: string, matchId: string) {
  const res = await authedFetch(`/challenges/${shareCode}/submit`, {
    method: 'POST',
    body: JSON.stringify({ match_id: matchId }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Error')
  await refreshBalance()
  return data
}

async function fetchOpenChallenges() {
  const res = await fetch(`${API_BASE}/challenges/open`)
  if (!res.ok) return []
  return await res.json()
}

async function fetchMyChallenges() {
  if (!token.value) return []
  const res = await authedFetch('/challenges/mine')
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

async function fetchAchievements() {
  if (!token.value) return []
  const res = await authedFetch('/achievements')
  if (!res.ok) return []
  return await res.json()
}

async function fetchSettings() {
  if (!token.value) return null
  const res = await authedFetch('/settings')
  if (!res.ok) return null
  return await res.json()
}

async function saveSettings(settings: Record<string, boolean>) {
  if (!token.value) return null
  const res = await authedFetch('/settings', { method: 'POST', body: JSON.stringify(settings) })
  if (!res.ok) return null
  return await res.json()
}

async function fetchPublicProfile(riotId: string) {
  const res = await fetch(`${API_BASE}/profile/${encodeURIComponent(riotId)}`)
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
  const data = await res.json().catch(() => null)
  if (!res.ok) return { error: (data && data.error) || `Error ${res.status}` }
  user.value = data
  return data
}

async function unlinkRiot() {
  if (!token.value) return null
  const res = await authedFetch('/auth/unlink-riot', { method: 'POST' })
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new Error((data && data.error) || `Error ${res.status}`)
  }
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
    unlinkRiot,
    handleAuthRedirect,
    createBet,
    createStatBet,
    placePlayerBet,
    acceptBet,
    cancelBet,
    fetchBet,
    fetchMyBets,
    resolveMyPendingBets,
    fetchOpenBets,
    fetchLeaderboard,
    fetchClusters,
    fetchDeathHeatmap,
    previewMultiplier,
    createChallenge,
    acceptChallenge,
    cancelChallenge,
    submitChallengeMatch,
    fetchOpenChallenges,
    fetchMyChallenges,
    createRoomBet,
    joinRoomBet,
    startRoomBet,
    cancelRoomBet,
    fetchRoomBets,
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
    fetchAchievements,
    fetchSettings,
    saveSettings,
    fetchPublicProfile,
  }
}
