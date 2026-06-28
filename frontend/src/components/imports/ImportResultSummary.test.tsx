import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { ImportResultSummary } from './ImportResultSummary'

describe('ImportResultSummary', () => {
  it('links a resolved record to its patient timeline', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ImportResultSummary
          patients={[
            {
              candidate_id: 'patient-1',
              action: 'create',
              patient_id: 'patient-id',
              record_ids: ['record-id'],
              record_groups: [{ group_id: 'group-1', action: 'create', record_id: 'record-id' }],
            },
          ]}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('Создана карточка пациента')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Открыть медицинскую историю' })).toHaveAttribute(
      'href',
      '/patients/patient-id#record-record-id',
    )
  })

  it('renders skipped candidates without a patient link', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ImportResultSummary
          patients={[
            {
              candidate_id: 'patient-2',
              action: 'skip',
              patient_id: null,
              record_ids: [],
              record_groups: [{ group_id: 'group-2', action: 'skip', record_id: null }],
            },
          ]}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('Пациент пропущен')).toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })
})
