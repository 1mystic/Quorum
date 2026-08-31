import { describe, test, expect, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import SelectField from './SelectField.vue'

// jsdom has no layout engine: every getBoundingClientRect() and offsetWidth
// read here is zero regardless of what the real component does, so these
// tests cannot see the popover land in the "correct" pixel position and do
// not claim to. What they exercise instead is the *sequencing* the two bugs
// were actually about: that a popover is never revealed before its
// post-layout measurement pass has run (bug 1, the first-open flash at the
// wrong place), and that the same async settle path runs identically on a
// second and third open, not just the first (bug 2's "persists, not just
// first time" symptom would show up here as `ready` never resettling).
//
// SelectField's doubleRaf falls back to setTimeout(fn, 0) chains in jsdom
// (no requestAnimationFrame), so waiting for "settled" is a vi.waitFor
// poll rather than a fixed number of ticks: the exact microtask/macrotask
// interleaving with Vue's own scheduler and Vue Test Utils' own nextTick
// calls is not something a test should hard-code the shape of.
async function waitUntilReady() {
  await vi.waitFor(() => {
    const list = document.querySelector('.select-list')
    if (!list || !list.classList.contains('ready')) throw new Error('not ready yet')
    return list
  })
}

const options = [
  { value: 'a', label: 'Faculty advisor' },
  { value: 'b', label: 'Member' }
]

function openTrigger(wrapper) {
  return wrapper.get('.select-trigger').trigger('click')
}

describe('SelectField popover sequencing', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  test('a fresh mount opened immediately does not reveal the popover before it is measured', async () => {
    const wrapper = mount(SelectField, { props: { modelValue: 'b', options }, attachTo: document.body })

    await openTrigger(wrapper)
    await nextTick()

    // The list exists (v-if has flipped) but must not be visible yet: it is
    // parked off-screen with visibility:hidden until placeList() has run
    // against a settled layout. This is the literal fix for "renders pinned
    // to the far left the first time": there is no tick at which a wrongly
    // positioned popover is paintable.
    const list = document.querySelector('.select-list')
    expect(list).not.toBeNull()
    expect(list.classList.contains('ready')).toBe(false)
    expect(list.style.left).toBe('-9999px')

    await waitUntilReady()

    expect(list.classList.contains('ready')).toBe(true)
    expect(list.style.left).not.toBe('-9999px')
    expect(list.style.position).toBe('fixed')

    wrapper.unmount()
  })

  test('open, close, then reopen goes through the same measure-before-reveal gate every time', async () => {
    const wrapper = mount(SelectField, { props: { modelValue: 'b', options }, attachTo: document.body })

    await openTrigger(wrapper)
    await waitUntilReady()
    let list = document.querySelector('.select-list')
    expect(list.classList.contains('ready')).toBe(true)

    // close
    await openTrigger(wrapper)
    await nextTick()
    expect(document.querySelector('.select-list')).toBeNull()

    // reopen: must re-gate, not just stay "ready" from before
    await openTrigger(wrapper)
    await nextTick()
    list = document.querySelector('.select-list')
    expect(list.classList.contains('ready')).toBe(false)

    await waitUntilReady()
    expect(list.classList.contains('ready')).toBe(true)

    wrapper.unmount()
  })

  test('the popover is teleported to <body>, not a child of the trigger or any of its ancestors', async () => {
    // This is the structural guarantee bug 2's "sticky/transform ancestor"
    // hypothesis was checked against: because <Teleport to="body"> moves the
    // list's real DOM node to be a direct child of <body>, no ancestor of
    // the trigger (position:sticky, backdrop-filter, transform, or
    // otherwise) can become the containing block for the popover's
    // position:fixed - that would only be possible if the popover were
    // still nested inside that ancestor in the DOM, and by construction it
    // never is once Teleport has run. Verified structurally here since
    // jsdom cannot compute a containing block or evaluate backdrop-filter.
    const sticky = document.createElement('div')
    sticky.style.position = 'sticky'
    sticky.style.top = '0'
    document.body.appendChild(sticky)

    const wrapper = mount(SelectField, { props: { modelValue: 'b', options }, attachTo: sticky })

    await openTrigger(wrapper)
    await waitUntilReady()

    const list = document.querySelector('.select-list')
    expect(list.parentElement).toBe(document.body)
    expect(sticky.contains(list)).toBe(false)

    wrapper.unmount()
    sticky.remove()
  })

  test('the trigger button, not an outer wrapper, is what leading-icon usages measure', async () => {
    // Bug 2's real cause: RoleSwitcher rendered its icon as a sibling of
    // SelectField's root, so triggerRef (the <button>) never included the
    // icon's width, and every popover opened offset right of the visible
    // pill by the icon's width plus its gap. The #icon slot renders inside
    // the same <button> that placeList() measures, so a consumer using it
    // can no longer reproduce that class of bug.
    const wrapper = mount(SelectField, {
      props: { modelValue: 'b', options },
      slots: { icon: '<svg data-test-icon />' }
    })

    const trigger = wrapper.get('.select-trigger')
    expect(trigger.find('[data-test-icon]').exists()).toBe(true)

    wrapper.unmount()
  })
})
