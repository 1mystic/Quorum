<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import {
  GraduationCap, User, ArrowRight, ArrowLeft, Sparkles, Compass, Check,
  Code2, Network, Radio, Settings2, Building2, Zap, Briefcase, Pencil,
  Cpu, Music, Paintbrush, Dumbbell, BookOpen, Mic2, TrendingUp,
  FlaskConical, Gamepad2, Camera, HeartHandshake, Search, CalendarCheck, Users, Award
} from 'lucide-vue-next'
import { updateMyProfile } from '../api/students'
import { toast } from '../composables/useToast'
import { invalidateCache } from '../utils/apiCache'

const router = useRouter()
const auth = useAuthStore()

const totalSteps = 3
const currentStep = ref(1)
const isDone = ref(false)

const selectedDept = ref('')
const otherDeptName = ref('')
const selectedYear = ref('')
const selectedInterests = ref([])
const selectedGoal = ref('')

const deptCards = [
  { id: 'cs', label: 'CS', icon: Code2, iconClass: 'blue-icon' },
  { id: 'it', label: 'IT', icon: Network, iconClass: 'green-icon' },
  { id: 'ec', label: 'ECE', icon: Radio, iconClass: 'orange-icon' },
  { id: 'me', label: 'ME', icon: Settings2, iconClass: 'yellow-icon' },
  { id: 'ce', label: 'Civil', icon: Building2, iconClass: 'blue-icon' },
  { id: 'ee', label: 'EEE', icon: Zap, iconClass: 'yellow-icon' },
  { id: 'mba', label: 'MBA', icon: Briefcase, iconClass: 'green-icon' }
]

const yearOptions = [
  { id: '1', label: '1st Year' },
  { id: '2', label: '2nd Year' },
  { id: '3', label: '3rd Year' },
  { id: '4', label: '4th Year' },
  { id: 'pg', label: 'PG' },
  { id: 'diploma', label: 'Diploma' }
]

const interestOptions = [
  { id: 'coding', label: 'Coding', icon: Code2 },
  { id: 'robotics', label: 'Robotics', icon: Cpu },
  { id: 'music', label: 'Music', icon: Music },
  { id: 'art', label: 'Art and Design', icon: Paintbrush },
  { id: 'sports', label: 'Sports', icon: Dumbbell },
  { id: 'literature', label: 'Literature', icon: BookOpen },
  { id: 'debate', label: 'Debate', icon: Mic2 },
  { id: 'entrepreneurship', label: 'Entrepreneurship', icon: TrendingUp },
  { id: 'science', label: 'Science', icon: FlaskConical },
  { id: 'gaming', label: 'Gaming', icon: Gamepad2 },
  { id: 'photography', label: 'Photography', icon: Camera },
  { id: 'social', label: 'Social Work', icon: HeartHandshake }
]

const goalOptions = [
  {
    id: 'discover',
    title: 'Discover clubs',
    desc: 'Find communities that match my interests and join them.',
    icon: Search,
    iconClass: 'orange-icon'
  },
  {
    id: 'events',
    title: 'Attend events',
    desc: 'Register for hackathons, workshops, and competitions.',
    icon: CalendarCheck,
    iconClass: 'green-icon'
  },
  {
    id: 'lead',
    title: 'Run a club',
    desc: 'Create my own club and manage events and members.',
    icon: Users,
    iconClass: 'blue-icon'
  },
  {
    id: 'certs',
    title: 'Earn certificates',
    desc: 'Build a verifiable record of my campus participation.',
    icon: Award,
    iconClass: 'yellow-icon'
  }
]

const progressPercent = computed(function calcProgress() {
  if (isDone.value) return 100
  return (currentStep.value / totalSteps) * 100
})

const stepCounterText = computed(function calcCounter() {
  if (isDone.value) return 'Done!'
  return 'Step ' + currentStep.value + ' of ' + totalSteps
})

function selectDept(deptId) {
  selectedDept.value = deptId
}

function selectYear(yearId) {
  selectedYear.value = yearId
}

function toggleInterest(interestId) {
  if (selectedInterests.value.includes(interestId)) {
    selectedInterests.value = selectedInterests.value.filter(function keepOthers(item) {
      return item !== interestId
    })
  } else {
    selectedInterests.value.push(interestId)
  }
}

function selectGoal(goalId) {
  selectedGoal.value = goalId
}

function validateStepOne() {
  if (!selectedDept.value) {
    toast.error('Please pick your department before continuing.')
    return false
  }
  if (selectedDept.value === 'other' && !otherDeptName.value.trim()) {
    toast.error('Please type your department name.')
    return false
  }
  if (!selectedYear.value) {
    toast.error('Please pick your current year before continuing.')
    return false
  }
  return true
}

function goToStep(stepNumber) {
  if (currentStep.value === 1 && stepNumber > 1 && !validateStepOne()) {
    return
  }
  currentStep.value = stepNumber
}

// The backend caps interests at 10 entries (UpdateProfileRequest), and this
// screen offers 12 options, so a student who picks everything would be
// rejected. Keep the first 10 rather than failing the whole submission.
const MAX_INTERESTS = 10

function readableDept() {
  if (selectedDept.value === 'other') {
    return otherDeptName.value.trim()
  }

  const match = deptCards.find(function byId(card) {
    return card.id === selectedDept.value
  })

  return match ? match.label : selectedDept.value
}

// students.year is an integer column (1-5). "PG" and "Diploma" have no numeric
// equivalent, so they are left unset rather than mapped to a misleading number.
function numericYear() {
  const parsed = Number(selectedYear.value)

  if (Number.isInteger(parsed) && parsed >= 1 && parsed <= 5) {
    return parsed
  }

  return null
}

function readableInterests() {
  const labels = []

  for (const id of selectedInterests.value) {
    const match = interestOptions.find(function byId(option) {
      return option.id === id
    })
    labels.push(match ? match.label : id)
  }

  return labels.slice(0, MAX_INTERESTS)
}

const isSavingProfile = ref(false)

async function finishOnboarding() {
  if (isSavingProfile.value) return
  isSavingProfile.value = true

  // Only the fields the students table actually has are sent. The chosen goal
  // is not persisted - there is no column for it - so it stays a UI-only step
  // until the backend adds one.
  const profile = {
    branch: readableDept(),
    interests: readableInterests()
  }

  const year = numericYear()

  if (year !== null) {
    profile.year = year
  }

  try {
    await updateMyProfile(profile)
    invalidateCache('my-profile')
    isDone.value = true
  } catch (error) {
    toast.error(error?.message || 'Could not save your profile. Please try again.')
  } finally {
    isSavingProfile.value = false
  }
}

function goExploreClubs() {
  router.push(`/${auth.user.collegeSlug}/clubs`)
}
</script>

<template>
  <div class="onboard-shell">

    <header class="onboard-topbar">
      <div class="logo-row logo-row-flat">
        <div class="logo-mark">
          <GraduationCap />
        </div>
        <span class="brand">Campus Connect</span>
      </div>
      <span class="onboard-step-counter">{{ stepCounterText }}</span>
    </header>

    <div class="onboard-progress-track">
      <div class="onboard-progress-fill" :style="{ width: progressPercent + '%' }"></div>
    </div>

    <main class="onboard-card">

      <div v-show="!isDone && currentStep === 1" class="onboard-step active">
        <div class="onboard-step-icon orange-icon">
          <User />
        </div>
        <h1 class="onboard-heading">Tell us a bit<br>about yourself.</h1>
        <p class="onboard-subtext">This helps us show the right clubs and events for you.</p>

        <div class="onboard-fields">

          <p class="onboard-field-label">Department / Branch</p>
          <div class="dept-cards-grid">
            <button
              v-for="dept in deptCards"
              :key="dept.id"
              class="dept-card"
              :class="{ selected: selectedDept === dept.id }"
              @click="selectDept(dept.id)"
            >
              <div class="dept-card-icon" :class="dept.iconClass">
                <component :is="dept.icon" />
              </div>
              <span class="dept-card-label">{{ dept.label }}</span>
            </button>
            <button
              class="dept-card dept-card-other"
              :class="{ selected: selectedDept === 'other' }"
              @click="selectDept('other')"
            >
              <div class="dept-card-icon dept-other-icon">
                <Pencil />
              </div>
              <span class="dept-card-label">Other</span>
            </button>
          </div>
          <input
            type="text"
            v-model="otherDeptName"
            class="dept-other-text-input"
            :class="{ visible: selectedDept === 'other' }"
            placeholder="Type your department"
          >

          <p class="onboard-field-label">Current Year</p>
          <div class="year-pills-row">
            <button
              v-for="year in yearOptions"
              :key="year.id"
              class="year-pill"
              :class="{ selected: selectedYear === year.id }"
              @click="selectYear(year.id)"
            >
              {{ year.label }}
            </button>
          </div>

        </div>

        <button class="onboard-next-btn" @click="goToStep(2)">
          Continue <ArrowRight />
        </button>
      </div>

      <div v-show="!isDone && currentStep === 2" class="onboard-step active">
        <div class="onboard-step-icon green-icon">
          <Sparkles />
        </div>
        <h1 class="onboard-heading">What gets you<br>excited?</h1>
        <p class="onboard-subtext">Pick as many as you like. We use this to suggest clubs you will actually enjoy.</p>

        <div class="interest-chips-grid">
          <button
            v-for="interest in interestOptions"
            :key="interest.id"
            class="interest-chip"
            :class="{ selected: selectedInterests.includes(interest.id) }"
            @click="toggleInterest(interest.id)"
          >
            <component :is="interest.icon" /> {{ interest.label }}
          </button>
        </div>

        <div class="onboard-nav-row">
          <button class="onboard-back-btn" @click="goToStep(1)">
            <ArrowLeft /> Back
          </button>
          <button class="onboard-next-btn" @click="goToStep(3)">
            Continue <ArrowRight />
          </button>
        </div>
      </div>

      <div v-show="!isDone && currentStep === 3" class="onboard-step active">
        <div class="onboard-step-icon blue-icon">
          <Compass />
        </div>
        <h1 class="onboard-heading">What are you<br>here for?</h1>
        <p class="onboard-subtext">You can always do all of these, but what is your main reason for joining?</p>

        <div class="goal-cards-grid">
          <button
            v-for="goal in goalOptions"
            :key="goal.id"
            class="goal-card"
            :class="{ selected: selectedGoal === goal.id }"
            @click="selectGoal(goal.id)"
          >
            <div class="goal-card-icon" :class="goal.iconClass">
              <component :is="goal.icon" />
            </div>
            <p class="goal-card-title">{{ goal.title }}</p>
            <p class="goal-card-desc">{{ goal.desc }}</p>
          </button>
        </div>

        <div class="onboard-nav-row">
          <button class="onboard-back-btn" @click="goToStep(2)">
            <ArrowLeft /> Back
          </button>
          <button class="onboard-next-btn" :disabled="isSavingProfile" @click="finishOnboarding">
            <span v-if="isSavingProfile" class="btn-spinner"></span>
            <template v-else>Let's go <ArrowRight /></template>
          </button>
        </div>
      </div>

      <div v-show="isDone" class="onboard-step active">
        <div class="onboard-done-graphic">
          <div class="done-circle-outer">
            <div class="done-circle-inner">
              <Check class="done-check-icon" />
            </div>
          </div>
        </div>
        <h1 class="onboard-heading">You are all set!</h1>
        <p class="onboard-subtext">
          Head over to the club directory and start discovering communities that match your interests.
        </p>
        <button class="onboard-next-btn onboard-done-btn" @click="goExploreClubs">
          Explore clubs <Compass />
        </button>
      </div>

    </main>

    <div class="onboard-deco-circle deco-orange"></div>
    <div class="onboard-deco-circle deco-green"></div>

  </div>
</template>
