// useToast — substituto de alert() / errores transitorios con estilo del producto.
//
// Uso:
//   import { useToast } from '../composables/useToast'
//   const { toast } = useToast()
//   toast.error('No se pudo borrar la sala')
//   toast.success('Apuesta creada · ' + bet.share_code)
//   toast.info('Generando card...', { duration: 1500 })
//
// App.vue monta <GlobalToast /> una vez para que cualquier componente
// pueda lanzar toasts sin instanciar el suyo.

import { reactive } from 'vue'

type Kind = 'error' | 'success' | 'info' | 'warning'

interface ToastEntry {
  id: number
  kind: Kind
  message: string
  // duration en ms; null = no auto-dismiss
  duration: number | null
}

interface ShowOpts {
  duration?: number | null
}

const state = reactive({
  entries: [] as ToastEntry[],
})

let _id = 0

function show(kind: Kind, message: string, opts: ShowOpts = {}) {
  const id = ++_id
  const duration = opts.duration === undefined
    ? (kind === 'error' ? 6000 : 3500)
    : opts.duration
  state.entries.push({ id, kind, message, duration })
  if (duration !== null) {
    setTimeout(() => dismiss(id), duration)
  }
  return id
}

function dismiss(id: number) {
  const i = state.entries.findIndex(e => e.id === id)
  if (i >= 0) state.entries.splice(i, 1)
}

function clear() {
  state.entries.splice(0, state.entries.length)
}

export function useToast() {
  return {
    state,
    dismiss,
    clear,
    toast: {
      error:   (msg: string, opts?: ShowOpts) => show('error', msg, opts),
      success: (msg: string, opts?: ShowOpts) => show('success', msg, opts),
      info:    (msg: string, opts?: ShowOpts) => show('info', msg, opts),
      warning: (msg: string, opts?: ShowOpts) => show('warning', msg, opts),
    },
  }
}
