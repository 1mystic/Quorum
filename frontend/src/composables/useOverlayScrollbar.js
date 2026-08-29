import { onMounted, onBeforeUnmount } from 'vue'

// Ports the document overlay scrollbar from design/samples/quorum/landing.html:
// the native thumb's length is fixed by the viewport/content ratio and cannot
// be shortened in CSS, so the real scrollbar is hidden (style.css section 33,
// `html{ scrollbar-width:none }` scoped to .landing-body) and this draws a
// short, capped, fading thumb bound to window scroll instead.

export function useOverlayScrollbar() {
  let bar = null
  let thumb = null
  let idleTimer = null
  let dragY = 0
  let dragTop = 0
  let resizeObserver = null

  const PAD = 10
  const MIN_H = 34
  const MAX_H = 84

  function geometry() {
    const doc = document.documentElement
    const scrollHeight = Math.max(doc.scrollHeight, document.body.scrollHeight)
    const clientHeight = window.innerHeight
    if (scrollHeight <= clientHeight + 4) {
      bar.style.display = 'none'
      return null
    }
    bar.style.display = ''
    const track = clientHeight - PAD * 2
    return { scrollHeight, clientHeight, track, h: Math.max(MIN_H, Math.min(MAX_H, track * (clientHeight / scrollHeight))) }
  }

  function draw() {
    const g = geometry()
    if (!g) return
    const max = g.scrollHeight - g.clientHeight
    const p = max > 0 ? Math.min(1, Math.max(0, (window.scrollY || window.pageYOffset) / max)) : 0
    thumb.style.height = g.h + 'px'
    thumb.style.transform = 'translateY(' + (PAD + p * (g.track - g.h)) + 'px)'
    bar.classList.add('on')
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
    dragTop = PAD + ((window.scrollY || 0) / (g.scrollHeight - g.clientHeight)) * (g.track - g.h)
    e.preventDefault()
  }

  function onPointerMove(e) {
    if (!thumb.classList.contains('drag')) return
    const g = geometry()
    if (!g) return
    const top = Math.min(g.track - g.h + PAD, Math.max(PAD, dragTop + (e.clientY - dragY)))
    const p = (top - PAD) / (g.track - g.h)
    window.scrollTo(0, p * (g.scrollHeight - g.clientHeight))
  }

  function onPointerEnd(e) {
    if (!thumb.classList.contains('drag')) return
    thumb.classList.remove('drag')
    try { thumb.releasePointerCapture(e.pointerId) } catch (err) { /* noop */ }
    draw()
  }

  onMounted(() => {
    if (typeof window === 'undefined' || !document.body) return

    document.documentElement.classList.add('qs-active')
    bar = document.createElement('div')
    bar.className = 'qs'
    thumb = document.createElement('div')
    thumb.className = 'qs-t'
    bar.appendChild(thumb)
    document.body.appendChild(bar)

    thumb.addEventListener('pointerdown', onPointerDown)
    thumb.addEventListener('pointermove', onPointerMove)
    thumb.addEventListener('pointerup', onPointerEnd)
    thumb.addEventListener('pointercancel', onPointerEnd)
    window.addEventListener('scroll', draw, { passive: true })
    window.addEventListener('resize', draw)
    if (window.ResizeObserver) {
      resizeObserver = new ResizeObserver(draw)
      resizeObserver.observe(document.body)
    }
    draw()
  })

  onBeforeUnmount(() => {
    document.documentElement.classList.remove('qs-active')
    window.removeEventListener('scroll', draw)
    window.removeEventListener('resize', draw)
    if (resizeObserver) resizeObserver.disconnect()
    if (bar && bar.parentNode) bar.parentNode.removeChild(bar)
    window.clearTimeout(idleTimer)
  })
}
