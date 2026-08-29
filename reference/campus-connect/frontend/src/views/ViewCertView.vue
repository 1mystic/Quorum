<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Download } from 'lucide-vue-next'
import { verifyCertificate } from '../api/certificates'
import { toast } from '../composables/useToast'

const route = useRoute()
const router = useRouter()

// The certificate is looked up by its serial through the same public verify
// endpoint the /verify page uses, rather than trusting whatever a query
// string claims - a link with hand-edited query params used to be able to
// display a fabricated certificate. verify() now also returns pdf_url: the
// exact PDF the backend generated for this certificate, so this page shows
// the real document rather than a separate hand-built approximation of it.
const certificate = ref(null)
const notFound = ref(false)
const loading = ref(true)

function goBack() {
  // A shared certificate link is often opened directly (new tab, external
  // chat), which leaves no in-app history to go back to - router.back() would
  // silently do nothing and leave the visitor stuck on this page.
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/')
  }
}

function downloadCert() {
  if (!certificate.value?.pdf_url) return
  window.open(certificate.value.pdf_url, '_blank', 'noopener')
}

onMounted(async function loadCertificate() {
  const serial = String(route.params.serial || '').trim()

  if (!serial) {
    notFound.value = true
    loading.value = false
    return
  }

  try {
    const result = await verifyCertificate(serial)

    if (result.valid) {
      certificate.value = result.certificate
      document.title = 'Certificate – ' + certificate.value.student_name + ' – Campus Connect'
    } else {
      notFound.value = true
    }
  } catch (error) {
    toast.error(error.message || 'Could not load this certificate.')
    notFound.value = true
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="cert-toolbar">
    <button class="btn-secondary" @click="goBack">
      <ArrowLeft /> Back
    </button>
    <div class="cert-toolbar-spacer"></div>
    <button v-if="certificate" class="btn-secondary" @click="downloadCert">
      <Download /> Download PDF
    </button>
  </div>

  <div v-if="notFound" class="cert-page-empty">
    <p class="empty-state">No certificate found for this serial number.</p>
  </div>

  <div v-else-if="loading" class="cert-page-empty">
    <p class="empty-state">Loading certificate...</p>
  </div>

  <div v-else-if="certificate" class="cert-pdf-frame">
    <iframe :src="certificate.pdf_url" class="cert-pdf-embed" title="Certificate PDF"></iframe>
  </div>
</template>
