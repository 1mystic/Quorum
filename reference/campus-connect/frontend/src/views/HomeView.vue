<script setup>
import { useRouter } from 'vue-router'
import { GraduationCap, Compass, ArrowRight, Users, ShieldCheck, UserPlus, CalendarCheck, Award, Building2, QrCode, Download, CheckCircle2 } from 'lucide-vue-next'
import { useScrollReveal } from '../composables/useScrollReveal'
import { ref, onMounted } from 'vue'
import ClubIcon from '../components/ui/ClubIcon.vue'
import { getTrendingClubs } from '../api/clubs'
import { cachedFetch } from '../utils/apiCache'

const router = useRouter()
const { collectReveal } = useScrollReveal()

const landingStats = [
  { num: '18+', label: 'Active clubs', accent: 'accent-orange' },
  { num: '47', label: 'Events this month', accent: 'accent-green' },
  { num: '1,243', label: 'Students onboard', accent: 'accent-blue' },
  { num: '2,100+', label: 'Certificates issued', accent: 'accent-orange' }
]

const marqueeCategories = [
  { label: 'Robotics', icon: 'robot' },
  { label: 'Coding', icon: 'laptop' },
  { label: 'Photography', icon: 'camera' },
  { label: 'Music', icon: 'music' },
  { label: 'Dance', icon: 'dance' },
  { label: 'Drama & Theatre', icon: 'drama' },
  { label: 'Astronomy', icon: 'telescope' },
  { label: 'Sports', icon: 'sports' },
  { label: 'Literature', icon: 'book' },
  { label: 'Entrepreneurship', icon: 'briefcase' },
  { label: 'Fine Arts', icon: 'palette' },
  { label: 'Science', icon: 'microscope' }
]

const howSteps = [
  {
    num: '1',
    title: 'Discover',
    desc: 'Browse the club directory or let the AI finder match clubs to your interests.',
    icon: Compass,
    iconClass: 'orange'
  },
  {
    num: '2',
    title: 'Join',
    desc: 'Send a join request and the club leader approves you in a single tap.',
    icon: UserPlus,
    iconClass: 'green'
  },
  {
    num: '3',
    title: 'Attend',
    desc: 'Register for events, show your ID at the gate, and get marked present.',
    icon: CalendarCheck,
    iconClass: 'blue'
  },
  {
    num: '4',
    title: 'Get certified',
    desc: 'Results publish instantly as verifiable certificates on your profile.',
    icon: Award,
    iconClass: 'yellow'
  }
]

const quotes = [
  {
    text: 'I found the Robotics Club in my first week and had a certificate from my first hackathon by mid-semester. Everything lived in one place.',
    name: 'Shikha Singh',
    role: 'CS · 1st Year · KNIT Sultanpur',
    initials: 'SK',
    avatarClass: 'orange-av'
  },
  {
    text: 'Attendance, results, and certificates used to take me a full weekend per event. Now the whole cycle is done before the participants leave the hall.',
    name: 'Aayansh Yadav',
    role: 'Leader · Robotics & Automation Club',
    initials: 'AY',
    avatarClass: 'green-av'
  },
  {
    text: 'Club approvals that sat in email threads for weeks now clear in days, and I can finally see every club and event on campus in one dashboard.',
    name: 'Student Affairs',
    role: 'Admin · KNIT Sultanpur',
    initials: 'SA',
    avatarClass: 'blue-av'
  }
]


const showcaseRowOne = [
  { img: 'https://picsum.photos/seed/cc-discover/400/260', label: 'Discover clubs' },
  { img: 'https://picsum.photos/seed/cc-join/400/260', label: 'Join in one tap' },
  { img: 'https://picsum.photos/seed/cc-events/400/260', label: 'Register for events' },
  { img: 'https://picsum.photos/seed/cc-attend/400/260', label: 'Live attendance' }
]

const showcaseRowTwo = [
  { img: 'https://picsum.photos/seed/cc-cert/400/260', label: 'Verified certificates' },
  { img: 'https://picsum.photos/seed/cc-board/400/260', label: 'Campus leaderboard' },
  { img: 'https://picsum.photos/seed/cc-announce/400/260', label: 'Club announcements' },
  { img: 'https://picsum.photos/seed/cc-admin/400/260', label: 'Admin oversight' }
]

const roleCards = [
  {
    title: 'Students',
    desc: 'Discover clubs, attend events, track results, and download verified participation certificates.',
    icon: Compass,
    cardClass: 'saturated-orange',
    iconClass: '',
    sparkleFill: 'rgba(255,255,255,0.4)',
    tags: ['Discovery', 'Certificates']
  },
  {
    title: 'Club Leaders',
    desc: 'Create events, manage membership, mark attendance, post announcements, and issue certificates.',
    icon: Users,
    cardClass: 'saturated-green',
    iconClass: 'identity-icon-green',
    sparkleFill: 'rgba(255,255,255,0.3)',
    tags: ['Events', 'Members']
  },
  {
    title: 'Administrators',
    desc: 'Register your college, review club applications, and monitor campus-wide activity at a glance.',
    icon: ShieldCheck,
    cardClass: 'saturated-navy',
    iconClass: 'identity-icon-blue',
    sparkleFill: 'rgba(110,151,201,0.3)',
    tags: ['Governance', 'Leaderboard']
  }
]

const exploreLinks = [
  { label: 'Clubs', to: '/clubs' },
  { label: 'Events', to: '/events' },
  { label: 'Leaderboard', to: '/leaderboard' },
  { label: 'AI Club Finder', to: '/find-clubs' }
]

const accountLinks = [
  { label: 'Log in', to: '/login' },
  { label: 'Create account', to: '/signup' },
  { label: 'For club leaders', to: '/signup' },
  { label: 'Verify a certificate', to: '/verify' }
]

const trendingClubs = ref([])
const trendingLoading = ref(true)

function categoryIcon(category) {
  const map = {
    Tech: 'laptop',
    Arts: 'palette',
    Culture: 'drama',
    Sports: 'sports',
    Music: 'music',
    Business: 'briefcase',
    Science: 'microscope'
  }

  return map[category] || 'robot'
}

function bannerClass(category) {
  const map = {
    Tech: 'banner-blue',
    Arts: 'banner-pink',
    Culture: 'banner-yellow',
    Sports: 'banner-green',
    Music: 'banner-purple',
    Business: 'banner-mint',
    Science: 'banner-orange'
  }

  return map[category] || 'banner-blue'
}

onMounted(async () => {
  try {
    trendingClubs.value = await cachedFetch('trending-clubs:8', () => getTrendingClubs(8))
  } catch (err) {
    console.error(err)
  } finally {
    trendingLoading.value = false
  }
})

function goTo(path) {
  router.push(path)
}
</script>

<template>
  <div class="landing-wrapper custom-scrollbar">

    <header class="landing-nav">
      <div class="logo-row logo-row-flat">
        <div class="logo-mark">
          <GraduationCap />
        </div>
        <span class="brand">Campus Connect</span>
      </div>

      <div class="topbar-spacer"></div>

      <div class="landing-nav-btn-group">
        <button class="btn-pill-white" @click="goTo('/login')">Log in</button>
        <button class="btn-pill-dark" @click="goTo('/signup')">Get started</button>
      </div>
    </header>

    <section class="hero-section">

      <div class="hero-copy reveal" :ref="collectReveal">
        <div class="hero-badge">
          <span class="hero-badge-dot"></span>
          Discover · Join · Achieve
        </div>

        <h1 class="hero-title">
          Find your<br>
          club. Build<br>
          your <span>story.</span>
        </h1>

        <p class="hero-desc">
          One platform for discovering student clubs, registering for events,
          tracking results, and earning verifiable participation certificates,
          all in one place.
        </p>

        <div class="hero-actions">
          <button class="btn-hero-primary" @click="goTo('/signup')">
            <Compass /> Start exploring
          </button>
          <button class="btn-tour" @click="goTo('/clubs')">
            <span class="btn-tour-icon">
              <ArrowRight />
            </span>
            Browse clubs
          </button>
        </div>

        <div class="social-proof">
          <div class="avatar-stack">
            <div class="stack-avatar">AR</div>
            <div class="stack-avatar">TN</div>
            <div class="stack-avatar">MR</div>
            <div class="stack-avatar stack-avatar-accent">+</div>
          </div>
          <p class="social-proof-text">
            <span>Trusted</span> by students and club leaders across campus
          </p>
        </div>
      </div>

      <div class="hero-graphic reveal reveal-delay-1" :ref="collectReveal">
        <div class="hero-showcase">
          <div class="showcase-row showcase-row-ltr">
            <div class="showcase-track">
              <div
                v-for="(shot, index) in [...showcaseRowOne, ...showcaseRowOne]"
                :key="'row1-' + index"
                class="showcase-card"
              >
                <img :src="shot.img" :alt="shot.label" width="210" height="138" loading="eager" decoding="async">
                <span class="showcase-label">{{ shot.label }}</span>
              </div>
            </div>
          </div>

          <div class="showcase-row showcase-row-rtl">
            <div class="showcase-track">
              <div
                v-for="(shot, index) in [...showcaseRowTwo, ...showcaseRowTwo]"
                :key="'row2-' + index"
                class="showcase-card"
              >
                <img :src="shot.img" :alt="shot.label" width="210" height="138" loading="eager" decoding="async">
                <span class="showcase-label">{{ shot.label }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="landing-stats-row hero-stats reveal reveal-delay-2" :ref="collectReveal">
        <div
          v-for="stat in landingStats"
          :key="stat.label"
          class="landing-stat"
          :class="stat.accent"
        >
          <p class="landing-stat-num">{{ stat.num }}</p>
          <p class="landing-stat-label">{{ stat.label }}</p>
        </div>
      </div>
    </section>

    <section class="landing-sections">
      <div class="sections-header reveal" :ref="collectReveal">
        <h2>Trending clubs this semester</h2>
        <span>Live from the club directory</span>
      </div>

      <div class="reveal" :ref="collectReveal">
        <div v-if="trendingLoading" class="page-loading-state">
          <div class="empty-state">
            <p>Loading trending clubs...</p>
          </div>
        </div>

        <div v-else-if="trendingClubs.length === 0" class="empty-state empty-state-wide">
          <Building2 />
          <p>No active clubs to show yet. Be the first college to register on Campus Connect.</p>
        </div>

        <div v-else class="club-marquee">
          <div class="club-marquee-track">
            <div
              v-for="(club, index) in [...trendingClubs, ...trendingClubs]"
              :key="club.id + '-' + index"
              class="mini-club-card"
            >
              <div class="mini-club-card-top">
                <div class="mini-club-dot" :class="bannerClass(club.category)">
                  <ClubIcon :name="categoryIcon(club.category)" />
                </div>

                <div class="mini-club-text">
                  <p class="mini-club-name"> {{ club.name }} </p>
                  <p class="mini-club-sub"> {{ club.member_count }} members · {{ club.category }} </p>
                </div>
              </div>

              <div class="mini-club-college">
                <Building2 />
                <span>{{ club.college_name }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="landing-sections">
      <div class="cert-showcase reveal" :ref="collectReveal">

        <div class="cert-showcase-copy">
          <h2 class="cert-showcase-title">Certificates that verify themselves.</h2>
          <p class="cert-showcase-desc">
            The moment a club leader declares results, every attendee gets a real, signed
            PDF certificate automatically — no design tool, no typing names one by one.
            Every certificate carries a unique serial number that anyone can check,
            no account required.
          </p>

          <div class="cert-showcase-points">
            <div class="cert-showcase-point">
              <CheckCircle2 />
              <span>Auto-generated the instant results are declared</span>
            </div>
            <div class="cert-showcase-point">
              <Download />
              <span>Downloadable anytime from a student's own profile</span>
            </div>
            <div class="cert-showcase-point">
              <ShieldCheck />
              <span>Publicly verifiable by serial number — no login needed</span>
            </div>
          </div>
        </div>

        <div class="cert-verify-card">
          <div class="cert-verify-icon">
            <QrCode />
          </div>
          <p class="cert-verify-title">Verify a certificate</p>
          <p class="cert-verify-desc">
            Have a certificate serial number? Confirm it's authentic and see who it
            belongs to — publicly, instantly, no sign-in required.
          </p>
          <button class="btn-primary cert-verify-btn" @click="goTo('/verify')">
            <ShieldCheck /> Verify a Certificate
          </button>
          <p class="cert-verify-hint">e.g. CC-GHP-2026-46275</p>
        </div>

      </div>
    </section>

    <section class="landing-sections">
      <div class="sections-header reveal" :ref="collectReveal">
        <h2>Built for every role</h2>
        <span>One unified system · tailored views</span>
      </div>

      <div class="roles-grid">
        <div
          v-for="(card, index) in roleCards"
          :key="card.title"
          class="identity-card reveal"
          :class="[card.cardClass, 'reveal-delay-' + (index + 1)]"
          :ref="collectReveal"
        >
          <svg class="identity-sparkle s1" viewBox="0 0 24 24">
            <path d="M12 0 C13 7 17 11 24 12 C17 13 13 17 12 24 C11 17 7 13 0 12 C7 11 11 7 12 0Z" :fill="card.sparkleFill"/>
          </svg>
          <div>
            <div class="identity-icon" :class="card.iconClass">
              <component :is="card.icon" />
            </div>
            <h3>{{ card.title }}</h3>
            <p>{{ card.desc }}</p>
          </div>
          <div class="identity-tags">
            <span v-for="tag in card.tags" :key="tag" class="identity-tag">{{ tag }}</span>
          </div>
        </div>
      </div>

      <div class="chip-marquee reveal" :ref="collectReveal">
        <div class="chip-marquee-track">
          <span
            v-for="(category, index) in [...marqueeCategories, ...marqueeCategories]"
            :key="index"
            class="marquee-chip"
          >
            <ClubIcon :name="category.icon" /> {{ category.label }}
          </span>
        </div>
      </div>
    </section>

    <section class="landing-sections">
      <div class="sections-header reveal" :ref="collectReveal">
        <h2>How it works</h2>
        <span>From discovery to certificate · four steps</span>
      </div>

      <div class="how-grid">
        <div
          v-for="(step, index) in howSteps"
          :key="step.title"
          class="how-card reveal"
          :class="'reveal-delay-' + index"
          :ref="collectReveal"
        >
          <span class="how-step-num">{{ step.num }}</span>
          <div class="how-card-icon" :class="step.iconClass">
            <component :is="step.icon" />
          </div>
          <p class="how-card-title">{{ step.title }}</p>
          <p class="how-card-desc">{{ step.desc }}</p>
        </div>
      </div>

      <div class="quotes-row">
        <div
          v-for="(quote, index) in quotes"
          :key="quote.name"
          class="quote-card reveal"
          :class="'reveal-delay-' + (index + 1)"
          :ref="collectReveal"
        >
          <p class="quote-text">"{{ quote.text }}"</p>
          <div class="quote-person">
            <div class="quote-avatar" :class="quote.avatarClass">{{ quote.initials }}</div>
            <div>
              <p class="quote-name">{{ quote.name }}</p>
              <p class="quote-role">{{ quote.role }}</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <div class="cta-footer-screen">

      <div class="cta-banner reveal" :ref="collectReveal">
        <div class="cta-circle-orange"></div>
        <div class="cta-circle-blue"></div>
        <div class="cta-content">
          <h2 class="cta-title">Your community is waiting.</h2>
          <p class="cta-desc">Sign up in under a minute — free forever, no credit card needed.</p>
        </div>
        <button class="btn-cta" @click="goTo('/signup')">
          <ArrowRight /> Create account
        </button>
      </div>

      <footer class="landing-footer reveal" :ref="collectReveal">
        <div class="footer-grid">

          <div>
            <div class="logo-row logo-row-flat">
              <div class="logo-mark">
                <GraduationCap />
              </div>
              <span class="brand">Campus Connect</span>
            </div>
            <p class="footer-brand-desc">
              The student club management platform for Indian higher-ed institutions.
              Discover clubs, attend events, and build a verifiable record of your campus life.
            </p>
          </div>

          <div>
            <p class="footer-col-title">Explore</p>
            <router-link
              v-for="link in exploreLinks"
              :key="link.label"
              :to="link.to"
              class="footer-link"
            >
              {{ link.label }}
            </router-link>
          </div>

          <div>
            <p class="footer-col-title">Account</p>
            <router-link
              v-for="link in accountLinks"
              :key="link.label"
              :to="link.to"
              class="footer-link"
            >
              {{ link.label }}
            </router-link>
          </div>

        </div>

        <div class="footer-bottom-bar">
          <span>© 2026 Campus Connect · Team NexMind, IITM BS</span>
          <span>Made for students, by students.</span>
        </div>
      </footer>

    </div>

  </div>
</template>
