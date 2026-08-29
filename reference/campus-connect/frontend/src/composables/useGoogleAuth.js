import { googleAuth } from '../api/auth'

const GIS_SRC = 'https://accounts.google.com/gsi/client'
let scriptPromise = null

function loadGis() {
  if (scriptPromise) return scriptPromise
  scriptPromise = new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) {
      resolve()
      return
    }
    const script = document.createElement('script')
    script.src = GIS_SRC
    script.async = true
    script.defer = true
    script.onload = () => resolve()
    script.onerror = () => {
      scriptPromise = null
      reject(new Error('Could not load Google sign-in'))
    }
    document.head.appendChild(script)
  })
  return scriptPromise
}

export function useGoogleAuth() {
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID
  const isConfigured = !!clientId

  async function renderButton(el, { onSuccess, onError, text = 'continue_with', intent = 'login' } = {}) {
    if (!el || !isConfigured) return

    try {
      await loadGis()
    } catch (error) {
      onError?.(error.message)
      return
    }

    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: async (response) => {
        try {
          const result = await googleAuth(response.credential, intent)
          await onSuccess?.(result)
        } catch (error) {
          onError?.(error?.message || 'Google sign-in failed')
        }
      }
    })

    const width = Math.min(400, Math.floor(el.offsetWidth)) || 320
    window.google.accounts.id.renderButton(el, {
      type: 'standard',
      theme: 'outline',
      size: 'large',
      shape: 'pill',
      text,
      logo_alignment: 'center',
      width
    })
  }

  return { renderButton, isConfigured }
}
