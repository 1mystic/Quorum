<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  GraduationCap,
  Building2,
  Mail,
  FileText,
  ArrowRight
} from 'lucide-vue-next'

import { onboardCollege } from '../api/auth'
import { useAuthStore } from '../stores/auth'
import { toast } from '../composables/useToast'

const router = useRouter()
const auth = useAuthStore()

const collegeName = ref('')
const emailSuffix = ref('')
const description = ref('')
const submitting = ref(false)

async function handleSubmit() {
  if (
    !collegeName.value.trim() ||
    !emailSuffix.value.trim() ||
    !description.value.trim()
  ) {
    toast.error("Please fill in all fields.")
    return
  }

  submitting.value = true

  try {
    const domain = emailSuffix.value
      .trim()
      .toLowerCase()
      .replace(/^@/, "")

    const response = await onboardCollege(
      {
        name: collegeName.value.trim(),
        email_suffix: domain,
        description: description.value.trim()
      },
      auth.token
    )

    auth.setUser({
      ...auth.user,
      collegeSlug: response.slug,
      collegeName: response.name
    })

    toast.success(response.message)

    router.replace(`/${response.slug}/admin`)
  } catch (error) {
    toast.error(error?.message || "Unable to complete setup.")
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="admin-onboard-page">

    <section class="admin-onboard-card" custom-scrollbar>

      <div class="logo-row auth-form-logo">
        <div class="logo-mark">
          <Building2 />
        </div>
        <span class="brand">Campus Connect</span>
      </div>

      <h2>Complete College Setup</h2>

      <p class="auth-form-subtitle">
        Register your institution to activate Campus Connect.
      </p>

      <div class="form-group">
        <label>College Name</label>

        <div class="input-icon-wrapper">
          <Building2 />
          <input
            v-model="collegeName"
            type="text"
            placeholder="ABC Engineering College"
          >
        </div>
      </div>

      <div class="form-group">
        <label>Official Student Email Domain</label>

        <div class="input-icon-wrapper">
          <Mail />
          <input
            v-model="emailSuffix"
            type="text"
            placeholder="college.edu"
          >
        </div>

        <small class="helper-text">
          Students using this email domain will automatically join your institution.
        </small>
      </div>

      <div class="form-group">
        <label>Description</label>

        <div class="input-icon-wrapper textarea-wrapper">
          <FileText />

          <textarea
            v-model="description"
            rows="5"
            placeholder="Briefly describe your institution..."
          />
        </div>
      </div>

      <button
        class="btn-auth-submit"
        :disabled="submitting"
        @click="handleSubmit"
      >
        <ArrowRight />

        {{ submitting ? 'Saving...' : 'Finish Setup' }}
      </button>

    </section>

  </div>
</template>