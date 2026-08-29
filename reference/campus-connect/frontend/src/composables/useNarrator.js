import { ref, onBeforeUnmount } from 'vue'

// A thin wrapper over the browser's built-in Web Speech API
// (window.speechSynthesis) so we can read the AI assistant's reply out loud
// with a play / pause / resume button. No network, no external service - the
// synthesis happens entirely in the browser.

export function useNarrator() {
  const synth = typeof window !== 'undefined' ? window.speechSynthesis : null
  const isSupported = ref(Boolean(synth))

  const isSpeaking = ref(false)
  const isPaused = ref(false)

  let currentUtterance = null

  function reset() {
    isSpeaking.value = false
    isPaused.value = false
    currentUtterance = null
  }

  function speak(text) {
    if (!synth || !text) return

    // Cancel anything already queued so a new reply does not stack up behind
    // the previous one.
    synth.cancel()

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 1
    utterance.pitch = 1

    // Only reset if this is still the active utterance - cancelling one to
    // start another fires the old one's onend, which must not clobber the
    // new utterance's state.
    function handleEnd() {
      if (currentUtterance === utterance) reset()
    }
    utterance.onend = handleEnd
    utterance.onerror = handleEnd

    currentUtterance = utterance
    isSpeaking.value = true
    isPaused.value = false
    synth.speak(utterance)
  }

  function pause() {
    if (!synth || !isSpeaking.value) return
    synth.pause()
    isPaused.value = true
  }

  function resume() {
    if (!synth || !isPaused.value) return
    synth.resume()
    isPaused.value = false
  }

  function stop() {
    if (!synth) return
    synth.cancel()
    reset()
  }

  // The single button toggles between all three states: idle -> speaking ->
  // paused -> speaking. The caller passes the text so a fresh idle press
  // starts narration.
  function toggle(text) {
    if (!isSpeaking.value) {
      speak(text)
    } else if (isPaused.value) {
      resume()
    } else {
      pause()
    }
  }

  onBeforeUnmount(stop)

  return { isSupported, isSpeaking, isPaused, speak, pause, resume, stop, toggle }
}
