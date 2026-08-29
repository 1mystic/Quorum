import { onMounted, onBeforeUnmount } from 'vue'

export function useScrollReveal() {
  const revealElements = []
  let observer = null

  function collectReveal(el) {
    if (el && !revealElements.includes(el)) {
      revealElements.push(el)
    }
  }

  function showElement(entry) {
    if (entry.isIntersecting) {
      entry.target.classList.add('reveal-visible')
      observer.unobserve(entry.target)
    }
  }

  onMounted(function startObserving() {
    observer = new IntersectionObserver(
      function onIntersect(entries) {
        entries.forEach(showElement)
      },
      { threshold: 0.15 }
    )

    revealElements.forEach(function watchElement(el) {
      observer.observe(el)
    })
  })

  onBeforeUnmount(function stopObserving() {
    if (observer) {
      observer.disconnect()
    }
  })

  return { collectReveal }
}
