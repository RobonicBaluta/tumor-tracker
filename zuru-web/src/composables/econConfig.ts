/**
 * Mirror del lado frontend de `zuru-web-backend/src/econ_config.py` (#39).
 *
 * Sólo incluye constantes que se muestran o referencian en la UI — los
 * valores que sólo viven en backend (UNDERDOG_BONUS, PAYOUT_DECAY_*,
 * rate-limits, etc.) no entran porque el frontend no necesita conocerlos.
 *
 * REGLA: cualquier cambio aquí debe acompañarse del cambio en el backend
 * (o viceversa). Si rompes esta regla, la UI miente al usuario sobre las
 * reglas reales del juego.
 *
 * ⚠️ NO HAY check automático todavía (TODO): el deploy NO importa ambos
 * archivos para asegurar paridad. La disciplina es manual hasta que se
 * añada un script de CI que parsee este TS + econ_config.py y compare
 * el subset común. Mientras tanto, busca grep en el otro lado antes de
 * tunear.
 */

// ---------------------------------------------------------------------------
// Tumor score thresholds
// ---------------------------------------------------------------------------

/** Tumor score >= este valor cae en categoría "sus" / break-even del payout
 *  (backend: SUS_TUMOR_THRESHOLD). Usado en explainers de Overview. */
export const SUS_TUMOR_THRESHOLD = 60.0

// ---------------------------------------------------------------------------
// Ventana de apuestas
// ---------------------------------------------------------------------------

/** Pasados N minutos de gametime, /bets/create rechaza. Mostrado en BetModal
 *  cuando la ventana está cerrada (backend: BET_CLOSE_AT_ELAPSED / 60). */
export const BET_CLOSE_AT_ELAPSED_MIN = 25

// ---------------------------------------------------------------------------
// Daily reward
// ---------------------------------------------------------------------------

/** Fallback para `user.daily.amount` cuando el backend aún no respondió
 *  (backend: DAILY_REWARD_AMOUNT). */
export const DAILY_REWARD_AMOUNT = 100

/** Cada 24h reseteamos el daily (backend: DAILY_REWARD_INTERVAL_SECONDS / 3600). */
export const DAILY_REWARD_INTERVAL_HOURS = 24

// ---------------------------------------------------------------------------
// Welcome + loyalty
// ---------------------------------------------------------------------------

/** Bonus al crear cuenta (backend: WELCOME_BONUS_AMOUNT). */
export const WELCOME_BONUS_AMOUNT = 50
/** Bonus extra al 3er daily claim (backend: LOYALTY_BONUS_AMOUNT). */
export const LOYALTY_BONUS_AMOUNT = 50
/** Nº de claims diarios antes de cobrar el bonus de loyalty
 *  (backend: LOYALTY_BONUS_AT_CLAIMS). */
export const LOYALTY_BONUS_AT_CLAIMS = 3

// ---------------------------------------------------------------------------
// House multiplier
// ---------------------------------------------------------------------------

/** Cap superior del multiplier de bets house (backend: HOUSE_MULT_MAX).
 *  El frontend lo usa sólo como referencia en explainers / tooltips. */
export const HOUSE_MULT_MAX = 6.5
