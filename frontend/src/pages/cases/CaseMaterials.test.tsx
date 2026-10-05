import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import api from '../../api/api'
import type { ClinicalCase } from '../../api/cases'
import CaseMaterials from './CaseMaterials'

afterEach(() => vi.restoreAllMocks())

it('keeps the latest search result when an earlier request completes afterwards', async () => {
  let resolveOld!: (result: { data: { items: unknown[]; total: number } }) => void
  const old = new Promise<{ data: { items: unknown[]; total: number } }>(resolve => { resolveOld = resolve })
  const material = (title: string) => ({ id: title, title, clinical_summary: '', event_date: '2026-01-01', record_type: 'other', status: 'unconfirmed' })
  vi.spyOn(api, 'get').mockImplementation(async (url, config) => {
    if (String(url).endsWith('/messages')) return { data: { items: [], total: 0 } }
    const params = config?.params
    const query = params && typeof params === 'object' && 'query' in params ? params.query : undefined
    if (query === 'old') return old
    return { data: { items: query === 'new' ? [material('Latest result')] : [], total: query === 'new' ? 1 : 0 } }
  })
  const c: ClinicalCase = { id: 'case', patient_id: 'patient', coordinator_id: 'doctor', title: 'Case', question: 'Question',
    status: 'active', version: 1, sequence: 1, record_ids: [], members: [], created_at: '', previous_case_id: null, published_record_id: null }
  render(<CaseMaterials c={c} owner={false} onChange={vi.fn()} onOpen={vi.fn()} />)
  fireEvent.change(screen.getByLabelText('Поиск в материалах и обсуждении'), { target: { value: 'old' } })
  fireEvent.change(screen.getByLabelText('Поиск в материалах и обсуждении'), { target: { value: 'new' } })
  await screen.findByText(/Latest result/)
  await act(async () => {
    resolveOld({ data: { items: [material('Stale result')], total: 1 } })
    await old
  })
  await waitFor(() => expect(screen.queryByText(/Stale result/)).not.toBeInTheDocument())
  expect(screen.getByText(/Latest result/)).toBeInTheDocument()
})
