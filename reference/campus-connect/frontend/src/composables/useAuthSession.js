import { useRouter } from 'vue-router'
import { jwtDecode } from 'jwt-decode'
import { useAuthStore } from '../stores/auth'
import { useClubsStore } from '../stores/clubs'
import { useEventsStore } from '../stores/events'
import { invalidateCache } from '../utils/apiCache'
import { getMyClubs } from '../api/clubs'
import { getMyProfile } from '../api/students'

export function useAuthSession() {
  const router = useRouter()
  const auth = useAuthStore()

  async function completeSignIn(result) {
    // Belt and braces alongside the reset in auth.logout(): a session can
    // also reach login without going through an explicit logout first (an
    // expired token redirecting back here, or the very first sign-in of the
    // tab), so the clubs/events caches are cleared on the way in as well as
    // the way out.
    useClubsStore().$reset()
    useEventsStore().$reset()
    invalidateCache()

    auth.setToken(result.access_token)

    const payload = jwtDecode(result.access_token)
    const role = payload.role?.toUpperCase()

    auth.setUser({
      name: payload.full_name,
      email: payload.email,
      collegeSlug: payload.college_slug,
      collegeName: auth.user.collegeName,
      initials: (payload.full_name || '')
        .split(' ')
        .map(word => word[0])
        .join('')
        .toUpperCase()
    })

    auth.setRole(
      role === 'ADMIN' || role === 'CAMPUS_ADMIN' ? 'admin' : 'student'
    )

    if (auth.role === 'student') {
      try {
        const ledClubs = await getMyClubs({ role: 'LEADER' })
        // The leader membership itself is approved the instant a club is
        // proposed, but an OFFICIAL club's status stays PENDING until an
        // admin approves it - "Manage Clubs" has nothing to manage until
        // then, so only a club that's actually live should unlock the nav.
        auth.setClubLeader(ledClubs.some((club) => club.status === 'ACTIVE'))
      } catch {
        auth.setClubLeader(false)
      }
    }

    if (auth.role === 'admin') {
      router.push(payload.college_slug ? `/${payload.college_slug}/admin` : '/admin/onboard')
      return
    }

    const slug = payload.college_slug

    // A student who has never filled in their profile is sent to onboarding
    // first. There is no "onboarded" flag on the account, so an empty branch
    // and no interests is what stands in for one - which means the screen
    // stops appearing by itself once the profile is saved.
    if (await needsOnboarding()) {
      router.push(`/${slug}/onboard`)
      return
    }

    if (auth.canManageClubs) {
      router.push(`/${slug}/leader/club`)
    } else {
      router.push(auth.homeRoute)
    }
  }

  async function needsOnboarding() {
    try {
      const profile = await getMyProfile()
      const hasInterests = Array.isArray(profile.interests) && profile.interests.length > 0

      return !profile.branch && !hasInterests
    } catch {
      // Never block sign-in on this check - if the profile cannot be read,
      // send the student to their normal landing page.
      return false
    }
  }

  return { completeSignIn }
}
