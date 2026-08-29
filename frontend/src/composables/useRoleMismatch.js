import { reactive } from 'vue'

// Non-blocking demo-RBAC banner state, set by the router guard in
// router/index.js and read by RoleMismatchBanner.vue in App.vue. Deliberately
// module-level (not a Pinia store): it is transient UI chrome, not session
// state, and needs to be readable from a navigation guard before any
// component has mounted.

export const roleMismatchState = reactive({
  visible: false,
  message: ''
})

export function showRoleMismatch(message) {
  roleMismatchState.message = message
  roleMismatchState.visible = true
}

export function dismissRoleMismatch() {
  roleMismatchState.visible = false
}
