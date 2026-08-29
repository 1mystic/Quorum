<script setup>
import {
  Bot,
  Laptop,
  Camera,
  Music,
  Drama,
  Briefcase,
  Telescope,
  Volleyball,
  PersonStanding,
  Puzzle,
  Microscope,
  Palette,
  BookOpen,
  School,
  Cog,
  Medal,
  Megaphone,
  Calendar,
  Trophy,
  AlertCircle
} from 'lucide-vue-next'

const props = defineProps({
  name: { type: String, required: true }
})

const iconMap = {
  robot: Bot,
  laptop: Laptop,
  camera: Camera,
  music: Music,
  drama: Drama,
  briefcase: Briefcase,
  telescope: Telescope,
  sports: Volleyball,
  dance: PersonStanding,
  chess: Puzzle,
  microscope: Microscope,
  palette: Palette,
  book: BookOpen,
  school: School,
  gear: Cog,
  medal: Medal,

  megaphone: Megaphone,
  calendar: Calendar,
  trophy: Trophy,
  'alert-circle': AlertCircle
}

function pickIcon(name) {
  return iconMap[name] || Bot
}
</script>

<template>
  <component :is="pickIcon(props.name)" />
</template>
