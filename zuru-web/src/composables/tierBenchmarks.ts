/**
 * Tier benchmarks (#33) — promedios estimados por tier para comparar
 * el rendimiento del user vs. el "Diamond IV avg" o similar.
 *
 * Datos: agregados aproximados de op.gg / u.gg para SoloQ patch 14.x.
 * Refrescar cada major-patch; los valores cambian con itemización + meta.
 *
 * Uso: `tierBenchmark('DIAMOND').kda` → 3.2.
 * Compara `userKda` con `bm.kda` para mostrar "+0.4 vs Diamond avg" o
 * "-0.2 vs Diamond avg".
 *
 * NOTA: estos NO son los valores oficiales de Riot — son medias observadas
 * en sites de tracker. Servirán de orientación, no de ground truth.
 */

export interface TierBenchmark {
  /** Kill+Assist divided by Death (≥1 muerte se cuenta como 1). */
  kda: number
  /** CS por minuto (con jungla = TOTAL_CS / minutos). */
  cs_per_min: number
  /** Damage to champions promedio por partida (k). */
  dmg_avg_k: number
  /** Vision score promedio. */
  vision: number
  /** Win rate global esperado para ese tier (no es 50% porque hay tiers
   *  cuello de botella). */
  winrate_pct: number
}

export const TIER_BENCHMARKS: Record<string, TierBenchmark> = {
  IRON:        { kda: 1.7, cs_per_min: 4.3, dmg_avg_k: 12, vision: 12, winrate_pct: 47 },
  BRONZE:      { kda: 1.9, cs_per_min: 4.8, dmg_avg_k: 14, vision: 14, winrate_pct: 48 },
  SILVER:      { kda: 2.1, cs_per_min: 5.3, dmg_avg_k: 16, vision: 16, winrate_pct: 49 },
  GOLD:        { kda: 2.4, cs_per_min: 5.8, dmg_avg_k: 18, vision: 18, winrate_pct: 50 },
  PLATINUM:    { kda: 2.7, cs_per_min: 6.2, dmg_avg_k: 20, vision: 20, winrate_pct: 51 },
  EMERALD:     { kda: 2.9, cs_per_min: 6.5, dmg_avg_k: 22, vision: 22, winrate_pct: 51 },
  DIAMOND:     { kda: 3.2, cs_per_min: 6.9, dmg_avg_k: 24, vision: 24, winrate_pct: 52 },
  MASTER:      { kda: 3.5, cs_per_min: 7.1, dmg_avg_k: 26, vision: 26, winrate_pct: 53 },
  GRANDMASTER: { kda: 3.8, cs_per_min: 7.3, dmg_avg_k: 28, vision: 28, winrate_pct: 54 },
  CHALLENGER:  { kda: 4.1, cs_per_min: 7.5, dmg_avg_k: 30, vision: 30, winrate_pct: 55 },
  UNRANKED:    { kda: 2.4, cs_per_min: 5.5, dmg_avg_k: 17, vision: 17, winrate_pct: 50 }, // fallback ≈ Gold
}

/** Helper: lookup case-insensitive con fallback a UNRANKED. */
export function tierBenchmark(tier?: string | null): TierBenchmark {
  if (!tier) return TIER_BENCHMARKS.UNRANKED
  const key = tier.toUpperCase()
  return TIER_BENCHMARKS[key] || TIER_BENCHMARKS.UNRANKED
}

/** Formatea una comparación user-vs-tier. */
export function formatDelta(value: number, benchmark: number, units = ''): {
  text: string
  positive: boolean
} {
  const diff = value - benchmark
  const sign = diff >= 0 ? '+' : ''
  return {
    text: `${sign}${diff.toFixed(1)}${units} vs avg`,
    positive: diff >= 0,
  }
}
