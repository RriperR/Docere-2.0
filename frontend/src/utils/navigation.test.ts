import { expect, it } from 'vitest'
import { getBreadcrumbs } from './navigation'

it('keeps clinical identifiers out of breadcrumb labels', () => {
  const crumbs = getBreadcrumbs('/cases/private-case-id')
  expect(crumbs.map(c => c.label)).toEqual(['Рабочий стол', 'Клинические случаи', 'Совместный разбор'])
  expect(crumbs[crumbs.length - 1]?.path).toBe('/cases/private-case-id')
})
it('keeps import result navigation pointed at the complete route', () => {
  expect(getBreadcrumbs('/upload/review/import-id')[2]).toEqual({ label: 'Проверка материалов', path: '/upload/review/import-id' })
  expect(getBreadcrumbs('/dashboard/doctor')).toEqual([{ label: 'Рабочий стол', path: '/dashboard' }])
})
