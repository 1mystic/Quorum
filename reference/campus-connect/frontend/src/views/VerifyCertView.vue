<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { GraduationCap, Search, ShieldCheck, XCircle } from 'lucide-vue-next'
import { verifyCertificate } from '../api/certificates'
import { toast } from '../composables/useToast'

const route = useRoute()

const serialInput = ref('')
const foundCert = ref(null)
const showInvalid = ref(false)

const RESULT_LABELS = {
  WINNER: 'Winner',
  RUNNER_UP: 'Runner-up',
  PARTICIPANT: 'Participant'
}

function resultLabel(result) {
  return RESULT_LABELS[result] || result
}

function formatDate(value) {
  if (!value) return ''

  return new Date(value).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'long',
    year: 'numeric'
  })
}

function clearResult() {
  foundCert.value = null
  showInvalid.value = false
}

async function verifyCert() {
  const cleaned = serialInput.value.trim().toUpperCase()

  if (!cleaned) {
    toast.error('Please enter a serial number.')
    return
  }

  try {
    const result = await verifyCertificate(cleaned)

    if (result.valid && result.certificate) {
      foundCert.value = result.certificate
      showInvalid.value = false
    } else {
      foundCert.value = null
      showInvalid.value = true
    }
  } catch (error) {
    foundCert.value = null
    showInvalid.value = true
    toast.error(error.message || 'Could not verify this certificate.')
  }
}

onMounted(function prefillFromRoute() {
  const serialParam = String(route.params.serial || '')

  if (serialParam.toUpperCase().startsWith('CC-')) {
    serialInput.value = serialParam.toUpperCase()
    verifyCert()
  }
})
</script>

<template>
  <div class="verify-logo-row">
      <div class="verify-logo-mark">
        <GraduationCap />
      </div>
    <span class="verify-brand">Campus Connect</span>
  </div>

  <div class="verify-card">
      <p class="verify-card-title">Certificate Verification</p>
      <p class="verify-card-sub">Enter the serial number printed on the certificate to confirm its authenticity.</p>

      <div class="verify-serial-row">
        <input
          type="text"
          v-model="serialInput"
          class="verify-serial-input"
          placeholder="CC-CERT-2026-XXXX"
          maxlength="20"
          autocomplete="off"
          spellcheck="false"
          @input="clearResult"
          @keydown.enter="verifyCert"
        >
        <button class="btn-primary" @click="verifyCert">
          <Search /> Verify
        </button>
      </div>

      <div v-if="foundCert" class="cert-display">
        <div class="cert-display-header">
          <div class="cert-display-icon">
            <ShieldCheck />
          </div>
          <div>
            <p class="cert-display-valid">Certificate is Valid</p>
            <p class="cert-display-serial">{{ foundCert.serial }}</p>
          </div>
        </div>
        <div class="cert-display-rows">
          <div class="cert-display-item">
            <span class="cert-display-label">Issued to</span>
            <span class="cert-display-value">{{ foundCert.student_name }}</span>
          </div>
          <div class="cert-display-divider"></div>
          <div class="cert-display-item">
            <span class="cert-display-label">Event</span>
            <span class="cert-display-value">{{ foundCert.event_title }}</span>
          </div>
          <div class="cert-display-item">
            <span class="cert-display-label">Club</span>
            <span class="cert-display-value">{{ foundCert.club_name }}</span>
          </div>
          <div class="cert-display-divider"></div>
          <div class="cert-display-item">
            <span class="cert-display-label">Result</span>
            <span class="cert-display-value">{{ resultLabel(foundCert.result) }}</span>
          </div>
          <div class="cert-display-item">
            <span class="cert-display-label">Date issued</span>
            <span class="cert-display-value">{{ formatDate(foundCert.issued_at) }}</span>
          </div>
          <div class="cert-display-item">
            <span class="cert-display-label">College</span>
            <span class="cert-display-value">{{ foundCert.college_name }}</span>
          </div>
        </div>
      </div>

      <div v-if="showInvalid" class="verify-invalid">
        <div class="verify-invalid-icon">
          <XCircle />
        </div>
        <p class="verify-invalid-text">No certificate found for this serial number. Please check the code and try again.</p>
      </div>

    </div>

  <p class="verify-footer-note">
    This page is publicly accessible. Certificates are issued by Campus Connect on behalf of registered clubs at participating colleges.
  </p>
</template>
