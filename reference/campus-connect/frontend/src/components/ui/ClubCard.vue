<script setup>
import { computed } from 'vue'
import { Users, Sparkles } from 'lucide-vue-next'
import ClubIcon from './ClubIcon.vue'

const props = defineProps({
  club: { type: Object, required: true },
  badge: { type: String, default: '' }
})

const emit = defineEmits(['open'])

// The API returns no colour or icon for a club, so the card derives both from
// the data it does have. Before the real backend landed these came from the
// mock fixtures, which is why cards rendered blank once the mocks were removed.
const bannerColours = [
  'banner-orange',
  'banner-green',
  'banner-blue',
  'banner-yellow',
  'banner-pink',
  'banner-mint'
]

// Categories the backend actually uses today. Anything unrecognised falls
// through to the name-based colour below, so a new category is never blank.
const categoryStyles = {
  technology: { colour: 'banner-blue', icon: 'laptop' },
  tech: { colour: 'banner-blue', icon: 'laptop' },
  culture: { colour: 'banner-pink', icon: 'music' },
  cultural: { colour: 'banner-pink', icon: 'music' },
  arts: { colour: 'banner-yellow', icon: 'palette' },
  art: { colour: 'banner-yellow', icon: 'palette' },
  business: { colour: 'banner-mint', icon: 'briefcase' },
  sports: { colour: 'banner-green', icon: 'sports' },
  sport: { colour: 'banner-green', icon: 'sports' },
  academic: { colour: 'banner-blue', icon: 'school' },
  academics: { colour: 'banner-blue', icon: 'school' },
  social: { colour: 'banner-orange', icon: 'megaphone' },
  literature: { colour: 'banner-yellow', icon: 'book' },
  literary: { colour: 'banner-yellow', icon: 'book' },
  science: { colour: 'banner-green', icon: 'microscope' },
  music: { colour: 'banner-pink', icon: 'music' },
  photography: { colour: 'banner-yellow', icon: 'camera' }
}

// Keywords checked against the club name when the category is unfamiliar.
// Ordered most specific first, since the first hit wins.
const nameKeywords = [
  { match: 'robot', icon: 'robot' },
  { match: 'photo', icon: 'camera' },
  { match: 'camera', icon: 'camera' },
  { match: 'cod', icon: 'laptop' },
  { match: 'program', icon: 'laptop' },
  { match: 'software', icon: 'laptop' },
  { match: 'tech', icon: 'laptop' },
  { match: 'music', icon: 'music' },
  { match: 'band', icon: 'music' },
  { match: 'drama', icon: 'drama' },
  { match: 'theatre', icon: 'drama' },
  { match: 'theater', icon: 'drama' },
  { match: 'debate', icon: 'megaphone' },
  { match: 'literary', icon: 'book' },
  { match: 'book', icon: 'book' },
  { match: 'entrepreneur', icon: 'briefcase' },
  { match: 'business', icon: 'briefcase' },
  { match: 'startup', icon: 'briefcase' },
  { match: 'astro', icon: 'telescope' },
  { match: 'space', icon: 'telescope' },
  { match: 'science', icon: 'microscope' },
  { match: 'art', icon: 'palette' },
  { match: 'design', icon: 'palette' },
  { match: 'chess', icon: 'chess' },
  { match: 'dance', icon: 'dance' },
  { match: 'sport', icon: 'sports' },
  { match: 'athletic', icon: 'sports' }
]

function normalise(value) {
  return String(value || '').trim().toLowerCase()
}

// A small stable hash of the club name. Same club always gets the same
// colour, across reloads and across every list it appears in.
function hashName(name) {
  let total = 0

  for (const character of normalise(name)) {
    total = total + character.charCodeAt(0)
  }

  return total
}

function findCategoryStyle(category) {
  return categoryStyles[normalise(category)] || null
}

function findKeywordIcon(name) {
  const haystack = normalise(name)

  for (const entry of nameKeywords) {
    if (haystack.includes(entry.match)) {
      return entry.icon
    }
  }

  return ''
}

const bannerColour = computed(function pickBannerColour() {
  const fromCategory = findCategoryStyle(props.club.category)

  if (fromCategory) {
    return fromCategory.colour
  }

  const index = hashName(props.club.name) % bannerColours.length

  return bannerColours[index]
})

const iconName = computed(function pickIconName() {
  // The club's own name is the most specific signal, so it is checked first.
  const fromName = findKeywordIcon(props.club.name)

  if (fromName) {
    return fromName
  }

  const fromCategory = findCategoryStyle(props.club.category)

  if (fromCategory) {
    return fromCategory.icon
  }

  return 'school'
})

const bannerImage = computed(function pickBannerImage() {
  return props.club.image_url || ''
})

function openClub() {
  emit('open')
}
</script>

<template>
  <div class="club-card" @click="openClub">
    <div class="club-card-banner" :class="bannerColour">
      <img
        v-if="bannerImage"
        class="club-card-banner-img"
        :src="bannerImage"
        :alt="club.name"
      />

      <template v-else>
        <div class="club-card-circle-1"></div>
        <div class="club-card-circle-2"></div>
        <div class="club-card-circle-3"></div>

        <span class="club-card-banner-icon">
          <ClubIcon :name="iconName" />
        </span>
      </template>

      <div v-if="badge" class="club-card-recommended-badge">
        <Sparkles /> {{ badge }}
      </div>
    </div>

    <div class="club-card-content">
      <div>
        <div class="club-card-header">
          <span class="club-card-title">{{ club.name }}</span>

          <span class="club-card-members">
            <Users /> {{ club.member_count }}
          </span>
        </div>

        <p class="club-card-desc">
          {{ club.description }}
        </p>
      </div>

      <div class="club-card-tags">
        <span class="club-card-tag">{{ club.category }}</span>
        <span v-if="club.type" class="club-card-tag">
          {{ club.type }}
        </span>
      </div>
    </div>
  </div>
</template>
