import { createI18n } from 'vue-i18n'
import es from './locales/es.json'
import en from './locales/en.json'

export type LocaleKey = 'es' | 'en'

const STORAGE_KEY = 'tumor.locale'

function detectInitialLocale(): LocaleKey {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'es' || saved === 'en') return saved
  } catch {}
  const nav = (navigator.language || 'es').slice(0, 2).toLowerCase()
  return nav === 'en' ? 'en' : 'es'
}

export const i18n = createI18n({
  legacy: false,
  locale: detectInitialLocale(),
  fallbackLocale: 'es',
  messages: { es, en },
})

export function setLocale(locale: LocaleKey) {
  i18n.global.locale.value = locale
  try { localStorage.setItem(STORAGE_KEY, locale) } catch {}
}

export function currentLocale(): LocaleKey {
  return i18n.global.locale.value as LocaleKey
}
