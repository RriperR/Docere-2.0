import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import api from '../../api/api'
import { ImportResultSummary } from './ImportResultSummary'

beforeEach(() => { vi.spyOn(api, 'get').mockResolvedValue({ data: { id: 'patient-id', fio: 'Пациент' } }) })
afterEach(() => vi.restoreAllMocks())

describe('ImportResultSummary', () => {
  it('links a resolved record to its patient timeline', () => {
    render(
      <MemoryRouter>
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

    expect(screen.getByRole('link', { name: 'Открыть запись 1' })).toHaveAttribute('href', '/patients/patient-id#record-record-id')
    expect(screen.getByText('Создана карточка пациента')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Открыть медицинскую историю' })).toHaveAttribute(
      'href',
      '/patients/patient-id#record-record-id',
    )
  })

  it('renders skipped candidates without a patient link', () => {
    render(
      <MemoryRouter>
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

it('keeps every resolved record under its own patient, including mixed and skipped groups', () => {
  render(<MemoryRouter><ImportResultSummary patients={[
    { candidate_id: 'one', action: 'existing', patient_id: 'one', record_ids: ['a', 'b'], record_groups: [{ group_id: 'a', action: 'create', record_id: 'a' }, { group_id: 'b', action: 'create', record_id: 'b' }] },
    { candidate_id: 'two', action: 'create', patient_id: 'two', record_ids: ['c'], record_groups: [{ group_id: 'c', action: 'create', record_id: 'c' }, { group_id: 'd', action: 'skip', record_id: null }] },
  ]} /></MemoryRouter>)
  expect(screen.getAllByRole('link', { name: 'Открыть запись 1' }).map(link => link.getAttribute('href'))).toEqual(['/patients/one#record-a', '/patients/two#record-c'])
  expect(screen.getByRole('link', { name: 'Открыть запись 2' })).toHaveAttribute('href', '/patients/one#record-b')
})
