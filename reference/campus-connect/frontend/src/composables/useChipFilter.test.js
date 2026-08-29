import { describe, test, expect } from 'vitest'
import { ref } from 'vue'
import { useChipFilter } from './useChipFilter'

const items = ref([
  { id: 1, status: 'upcoming' },
  { id: 2, status: 'past' },
  { id: 3, status: 'upcoming' }
])

function matchesStatus(item, filter) {
  return item.status === filter
}

describe('useChipFilter', () => {
  test('starts with the all filter showing everything', () => {
    const { activeFilter, filteredItems } = useChipFilter(items, matchesStatus)

    expect(activeFilter.value).toBe('all')
    expect(filteredItems.value.length).toBe(3)
  })

  test('selectFilter narrows the list using the match function', () => {
    const { filteredItems, selectFilter } = useChipFilter(items, matchesStatus)

    selectFilter('past')

    expect(filteredItems.value.length).toBe(1)
    expect(filteredItems.value[0].id).toBe(2)
  })

  test('selecting all again restores the full list', () => {
    const { filteredItems, selectFilter } = useChipFilter(items, matchesStatus)

    selectFilter('upcoming')
    selectFilter('all')

    expect(filteredItems.value.length).toBe(3)
  })
})
