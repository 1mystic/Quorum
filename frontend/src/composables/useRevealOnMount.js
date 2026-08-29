import { onMounted } from 'vue'

// Scroll-reveal for a whole subtree of `.rv` elements at once, matching the
// stagger behaviour scripted in design/samples/quorum/landing.html. Simpler
// than collecting per-element template refs across many small landing
// subcomponents: called once, from the page root, after all children mount.

export function useRevealOnMount(rootRef) {
  onMounted(() => {
    const root = rootRef && rootRef.value ? rootRef.value : document
    const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const els = Array.from(root.querySelectorAll('.rv'))

    if (!('IntersectionObserver' in window) || reduceMotion) {
      els.forEach((el) => el.classList.add('in'))
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry, i) => {
          if (entry.isIntersecting) {
            window.setTimeout(() => entry.target.classList.add('in'), i * 70)
            observer.unobserve(entry.target)
          }
        })
      },
      { rootMargin: '0px 0px -8% 0px', threshold: 0.08 }
    )

    els.forEach((el) => observer.observe(el))
  })
}
