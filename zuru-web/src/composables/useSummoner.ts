// Composable para normalizar la entrada de summoner (gameName/tagLine) y
// exponer helpers genéricos de "login" que cualquier vista puede usar.

import { ref } from 'vue'
import { apiGet } from './useApi'

export interface SummonerInput {
  gameName: string
  tagLine: string
}

export function summonerKey(input: SummonerInput): string {
  return `${input.gameName}#${input.tagLine}`
}

export function parseSummonerSlug(slug: string): SummonerInput | null {
  const raw = decodeURIComponent(slug)
  const sep = raw.includes('#') ? '#' : '-'
  const idx = raw.lastIndexOf(sep)
  if (idx < 0) return null
  const name = raw.slice(0, idx)
  const tag = raw.slice(idx + 1)
  if (!name || !tag) return null
  return { gameName: name, tagLine: tag }
}

export function useRecentSummoners() {
  const recent = ref<string[]>([])

  async function refresh() {
    try {
      recent.value = await apiGet<string[]>('/recentSummoners')
    } catch {
      recent.value = []
    }
  }

  async function save(name: string) {
    try {
      await fetch('http://localhost:5000/recentSummoners', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ summoner: name }),
      })
      await refresh()
    } catch {}
  }

  return { recent, refresh, save }
}
