<script setup>
import { ref, reactive } from 'vue'
import { Save, Pencil, Trash2, Plus, Check, X, FileText, ExternalLink } from 'lucide-vue-next'
import AdminSidebar from '../components/layout/AdminSidebar.vue'
import Topbar from '../components/layout/Topbar.vue'
import { useGuidelinesStore } from '../stores/guidelines'
import { toast } from '../composables/useToast'

const guidelines = useGuidelinesStore()

const templateDraft = ref(guidelines.templateLink)

const editingId = ref(null)
const editingText = ref('')

// One draft input per section for adding new points
const newText = reactive({})
guidelines.sectionsList.forEach(function seed(section) {
  newText[section] = ''
})

function saveTemplate() {
  if (!templateDraft.value.trim()) {
    toast.error('Please enter the Google Docs template link.')
    return
  }
  guidelines.setTemplateLink(templateDraft.value)
  toast.success('Application template link saved.')
}

function addPoint(section) {
  const text = newText[section]
  if (!text || !text.trim()) {
    toast.error('Please type the guideline before adding it.')
    return
  }
  guidelines.addItem(section, text)
  newText[section] = ''
  toast.success('Guideline added.')
}

function startEdit(item) {
  editingId.value = item.id
  editingText.value = item.text
}

function saveEdit() {
  if (!editingText.value.trim()) {
    toast.error('A guideline cannot be empty.')
    return
  }
  guidelines.updateItem(editingId.value, editingText.value)
  editingId.value = null
  editingText.value = ''
  toast.success('Guideline updated.')
}

function cancelEdit() {
  editingId.value = null
  editingText.value = ''
}

function removePoint(item) {
  guidelines.removeItem(item.id)
  toast.info('Guideline removed.')
}
</script>

<template>
  <AdminSidebar />

  <div class="main-content">

    <Topbar title="Club Guidelines" sub="Rules and application guidance for club leaders" :show-bell="false" />

    <main class="content-body custom-scrollbar">

      <div>
        <div class="clubs-section-header">
          <h2 class="clubs-section-title">Application Template</h2>
        </div>
        <div class="admin-settings-card">
          <p class="body-text">
            Provide the Google Docs template that club leaders must copy, fill in, and
            submit as a shareable link with their application.
          </p>

          <div class="form-group" style="margin-top: 14px;">
            <label for="template-link">Google Docs Template Link</label>
            <input
              id="template-link"
              v-model="templateDraft"
              class="input-field"
              placeholder="https://docs.google.com/document/d/..."
            >
          </div>

          <div class="guideline-template-actions">
            <button class="btn-primary" @click="saveTemplate">
              <Save /> Save Template Link
            </button>
            <a
              v-if="guidelines.templateLink"
              :href="guidelines.templateLink"
              target="_blank"
              rel="noopener"
              class="btn-secondary"
            >
              <ExternalLink /> Open current template
            </a>
          </div>
        </div>
      </div>

      <div v-for="section in guidelines.sectionsList" :key="section">
        <div class="clubs-section-header">
          <h2 class="clubs-section-title">{{ section }}</h2>
          <span class="clubs-count-text">{{ guidelines.itemsBySection(section).length }} points</span>
        </div>

        <div class="card guideline-section">

          <div
            v-for="item in guidelines.itemsBySection(section)"
            :key="item.id"
            class="guideline-row"
          >
            <template v-if="editingId === item.id">
              <input
                v-model="editingText"
                class="input-field guideline-edit-input"
                @keydown.enter="saveEdit"
              >
              <div class="guideline-row-actions">
                <button class="btn-success" @click="saveEdit">
                  <Check /> Save
                </button>
                <button class="btn-secondary-sm" @click="cancelEdit">
                  <X /> Cancel
                </button>
              </div>
            </template>

            <template v-else>
              <span class="guideline-bullet"></span>
              <p class="guideline-text">{{ item.text }}</p>
              <div class="guideline-row-actions">
                <button class="guideline-icon-btn" aria-label="Edit" @click="startEdit(item)">
                  <Pencil />
                </button>
                <button class="guideline-icon-btn danger" aria-label="Delete" @click="removePoint(item)">
                  <Trash2 />
                </button>
              </div>
            </template>
          </div>

          <p v-if="guidelines.itemsBySection(section).length === 0" class="guideline-empty">
            <FileText /> No points added to this section yet.
          </p>

          <div class="guideline-add-row">
            <input
              v-model="newText[section]"
              class="input-field"
              placeholder="Add a new guideline point..."
              @keydown.enter="addPoint(section)"
            >
            <button class="btn-secondary" @click="addPoint(section)">
              <Plus /> Add
            </button>
          </div>

        </div>
      </div>

    </main>

  </div>
</template>
