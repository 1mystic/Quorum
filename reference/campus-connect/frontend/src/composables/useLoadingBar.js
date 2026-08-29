import { ref } from 'vue'

// A small NProgress-style top loading bar shared across the app. The router
// calls startLoading / finishLoading around navigations so lazy-loaded route
// chunks do not leave the viewport feeling frozen.

const visible = ref(false)
const progress = ref(0)

let startTimer = null
let trickleTimer = null
let endTimer = null

function clearTimers() {
  clearTimeout(startTimer)
  clearInterval(trickleTimer)
  clearTimeout(endTimer)
  startTimer = null
  trickleTimer = null
  endTimer = null
}

function startLoading() {
  clearTimers()
  // Delay a touch so instant (already-cached) navigations do not flash the bar.
  startTimer = setTimeout(function begin() {
    visible.value = true
    progress.value = 12
    trickleTimer = setInterval(function trickle() {
      if (progress.value < 90) {
        progress.value += Math.random() * 6 + 2
      }
    }, 240)
  }, 140)
}

function finishLoading() {
  clearTimeout(startTimer)
  clearInterval(trickleTimer)
  startTimer = null
  trickleTimer = null

  if (!visible.value) {
    progress.value = 0
    return
  }

  progress.value = 100
  endTimer = setTimeout(function hide() {
    visible.value = false
    progress.value = 0
  }, 280)
}

export function useLoadingBar() {
  return { visible, progress }
}

export { startLoading, finishLoading }
