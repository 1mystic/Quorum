import { ref } from 'vue'

// A tiny global toast system. Views call `toast.success(...)`, `toast.error(...)`
// or `toast.info(...)` instead of window.alert. ToastContainer reads the shared
// list and renders the stack in the top-right corner.

const toasts = ref([])
let nextId = 1

function push(message, type, duration) {
  const id = nextId++
  toasts.value.push({ id, message, type })

  // duration of 0 keeps the toast until it is dismissed by hand.
  if (duration !== 0) {
    window.setTimeout(function autoDismiss() {
      dismiss(id)
    }, duration || 3800)
  }

  return id
}

function dismiss(id) {
  toasts.value = toasts.value.filter(function keep(item) {
    return item.id !== id
  })
}

export const toast = {
  show(message, type, duration) {
    return push(message, type || 'info', duration)
  },
  success(message, duration) {
    return push(message, 'success', duration)
  },
  error(message, duration) {
    return push(message, 'error', duration)
  },
  info(message, duration) {
    return push(message, 'info', duration)
  }
}

export function useToastState() {
  return { toasts, dismiss }
}
