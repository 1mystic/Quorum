import { onMounted, onBeforeUnmount } from 'vue'

// Ports the overlayScroll(target) factory from design/samples/quorum/dashboard.html:
// a native thumb's length is fixed by the viewport/content ratio and cannot be
// shortened in CSS, so the real scrollbar is hidden (style.css section 33,
// `html.qs-active{ scrollbar-width:none }`) and this draws a short, capped,
// fading thumb instead. Binds to either the window (no target ref, or an
// unresolved one) or an inner scrolling element (a template ref), matching
// the sample's window+sidebar pair.
//
// prefers-reduced-motion: the thumb stays visible at rest (no fade-in/out,
// no hover-thickening transition) instead of only appearing while scrolling.

const PAD = 10
const MIN_H = 30
const MAX_H = 84

export function useOverlayScrollbar(targetRef) {
  let bar = null
  let thumb = null
  let idleTimer = null
  let dragY = 0
  let dragTop = 0
  let resizeObserver = null
  let reduceMotion = false

  function isWindowTarget() {
    return !targetRef || !targetRef.value
  }

  function el() {
    return isWindowTarget() ? document.documentElement : targetRef.value
  }

  function place() {
    if (isWindowTarget()) return
    const r = targetRef.value.getBoundingClientRect()
    bar.style.top = r.top + 'px'
    bar.style.height = r.height + 'px'
    bar.style.left = r.right - 13 + 'px'
  }

  function geometry() {
    const scrollHeight = isWindowTarget()
      ? Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)
      : el().scrollHeight
    const clientHeight = isWindowTarget() ? window.innerHeight : el().clientHeight
    if (scrollHeight <= clientHeight + 4) {
      bar.style.display = 'none'
      return null
    }
    bar.style.display = ''
    place()
    const track = clientHeight - PAD * 2
    return { scrollHeight, clientHeight, track, h: Math.max(MIN_H, Math.min(MAX_H, track * (clientHeight / scrollHeight))) }
  }

  function pos() {
    return isWindowTarget() ? window.scrollY || window.pageYOffset : el().scrollTop
  }

  function go(v) {
    if (isWindowTarget()) window.scrollTo(0, v)
    else el().scrollTop = v
  }

  function draw() {
    const g = geometry()
    if (!g) return
    const max = g.scrollHeight - g.clientHeight
    const p = max > 0 ? Math.min(1, Math.max(0, pos() / max)) : 0
    thumb.style.height = g.h + 'px'
    thumb.style.transform = 'translateY(' + (PAD + p * (g.track - g.h)) + 'px)'
    bar.classList.add('on')
    if (reduceMotion) return
    window.clearTimeout(idleTimer)
    idleTimer = window.setTimeout(() => {
      if (!thumb.classList.contains('drag')) bar.classList.remove('on')
    }, 1200)
  }

  function onPointerDown(e) {
    const g = geometry()
    if (!g) return
    thumb.classList.add('drag')
    try { thumb.setPointerCapture(e.pointerId) } catch (err) { /* noop */ }
    dragY = e.clientY
    dragTop = PAD + (pos() / (g.scrollHeight - g.clientHeight)) * (g.track - g.h)
    e.preventDefault()
  }

  function onPointerMove(e) {
    if (!thumb.classList.contains('drag')) return
    const g = geometry()
    if (!g) return
    const top = Math.min(g.track - g.h + PAD, Math.max(PAD, dragTop + (e.clientY - dragY)))
    go(((top - PAD) / (g.track - g.h)) * (g.scrollHeight - g.clientHeight))
  }

  function onPointerEnd(e) {
    if (!thumb.classList.contains('drag')) return
    thumb.classList.remove('drag')
    try { thumb.releasePointerCapture(e.pointerId) } catch (err) { /* noop */ }
    draw()
  }

  function scrollTarget() {
    return isWindowTarget() ? window : el()
  }

  onMounted(() => {
    if (typeof window === 'undefined' || !document.body) return
    reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches

    if (isWindowTarget()) document.documentElement.classList.add('qs-active')

    bar = document.createElement('div')
    bar.className = 'qs' + (isWindowTarget() ? '' : ' qs-el')
    thumb = document.createElement('div')
    thumb.className = 'qs-t'
    bar.appendChild(thumb)
    document.body.appendChild(bar)

    thumb.addEventListener('pointerdown', onPointerDown)
    thumb.addEventListener('pointermove', onPointerMove)
    thumb.addEventListener('pointerup', onPointerEnd)
    thumb.addEventListener('pointercancel', onPointerEnd)
    scrollTarget().addEventListener('scroll', draw, { passive: true })
    window.addEventListener('resize', draw)
    if (!isWindowTarget()) window.addEventListener('scroll', place, { passive: true })
    if (window.ResizeObserver) {
      resizeObserver = new ResizeObserver(draw)
      resizeObserver.observe(isWindowTarget() ? document.body : el())
    }
    draw()
  })

  onBeforeUnmount(() => {
    document.documentElement.classList.remove('qs-active')
    if (bar) {
      scrollTarget().removeEventListener('scroll', draw)
    }
    window.removeEventListener('resize', draw)
    window.removeEventListener('scroll', place)
    if (resizeObserver) resizeObserver.disconnect()
    if (bar && bar.parentNode) bar.parentNode.removeChild(bar)
    window.clearTimeout(idleTimer)
  })
}
