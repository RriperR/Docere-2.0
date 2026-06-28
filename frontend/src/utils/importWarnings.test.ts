import { describe, expect, it } from 'vitest'

import { groupedWarnings, warningAffectsFile, warningView } from './importWarnings'

describe('import warnings', () => {
  it('groups warnings into clinician-facing categories', () => {
    const groups = groupedWarnings([
      'Unsafe path skipped: ../secret.txt',
      'System file skipped: __MACOSX/index',
      'Multiple date candidates found: report.pdf',
    ])

    expect(groups).toHaveLength(2)
    expect(groups[0]).toMatchObject({ label: 'Безопасность' })
    expect(groups[0].warnings).toHaveLength(2)
    expect(groups[1]).toMatchObject({ label: 'Выбор даты' })
  })

  it('links a warning to the affected archive file', () => {
    expect(warningAffectsFile(['Empty file skipped: docs/report.pdf'], 'docs/report.pdf', 'report.pdf')).toBe(true)
    expect(warningAffectsFile(['Empty file skipped: other.pdf'], 'docs/report.pdf', 'report.pdf')).toBe(false)
  })

  it('uses a fallback category for unknown warnings', () => {
    expect(warningView('Unknown archive warning').label).toBe('Внимание')
  })
})
