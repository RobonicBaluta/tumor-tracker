// useConfirm — substituto de window.confirm() con estilo del producto.
//
// Uso:
//   import { useConfirm } from '../composables/useConfirm'
//   const { confirm } = useConfirm()
//   const ok = await confirm({ message: '¿Borrar la sala?', variant: 'danger' })
//   if (!ok) return
//
// App.vue monta <GlobalConfirmDialog /> una vez para que cualquier componente
// pueda dispararlo sin instanciar otro.

import { reactive } from 'vue'

type Variant = 'default' | 'danger' | 'warning'

interface ConfirmOpts {
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
  variant?: Variant
}

const state = reactive({
  show: false,
  title: '' as string | undefined,
  message: '',
  confirmText: 'Confirmar',
  cancelText: 'Cancelar',
  variant: 'default' as Variant,
})

let resolver: ((ok: boolean) => void) | null = null

function confirmFn(opts: ConfirmOpts): Promise<boolean> {
  // Si ya hay un confirm abierto, resuelve el anterior como cancelado
  if (resolver) {
    resolver(false)
    resolver = null
  }
  state.show = true
  state.title = opts.title
  state.message = opts.message
  state.confirmText = opts.confirmText ?? 'Confirmar'
  state.cancelText = opts.cancelText ?? 'Cancelar'
  state.variant = opts.variant ?? 'default'
  return new Promise<boolean>((resolve) => {
    resolver = resolve
  })
}

function accept() {
  state.show = false
  if (resolver) { resolver(true); resolver = null }
}

function cancel() {
  state.show = false
  if (resolver) { resolver(false); resolver = null }
}

export function useConfirm() {
  return { state, confirm: confirmFn, accept, cancel }
}
