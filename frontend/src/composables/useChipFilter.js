import { ref, computed } from 'vue'

export function useChipFilter(items, matchesFilter) {
  const activeFilter = ref('all')

  const filteredItems = computed(function applyFilter() {
    return items.value.filter(function checkItem(item) {
      if (activeFilter.value === 'all') return true
      return matchesFilter(item, activeFilter.value)
    })
  })

  function selectFilter(filterId) {
    activeFilter.value = filterId
  }

  return { activeFilter, filteredItems, selectFilter }
}
