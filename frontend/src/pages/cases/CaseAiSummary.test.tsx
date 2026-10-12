import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { AxiosError } from 'axios'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { caseAiApi, type CaseSummaryRun } from '../../api/caseAi'
import type { ClinicalCase } from '../../api/cases'
import CaseAiSummary from './CaseAiSummary'

const c: ClinicalCase = { id: 'case', patient_id: 'patient', coordinator_id: 'doctor', title: 'Case', question: 'Question', status: 'active', version: 3, sequence: 0, record_ids: ['record'], members: [], created_at: '', previous_case_id: null, published_record_id: null }
const completed: CaseSummaryRun = { id: 'run', case_id: c.id, status: 'completed', model: 'synthetic-model', provider: 'Test AI', prompt_version: 'case-facts-v1', created_at: '2026-10-11T12:00:00Z', documents: [
  { record_id: 'record', attachment_id: 'file', title: 'Synthetic record', record_date: '2026-10-11', filename: 'report.pdf', mime_type: 'application/pdf', status: 'completed', facts: [{ text: 'Synthetic finding', category: 'fact', sources: [{ page: 2, excerpt: 'Original finding' }] }], issues: [], document_date: null, page_count: 3, checksum: 'abc', error_code: null },
] }
beforeEach(() => {
  vi.spyOn(caseAiApi, 'capabilities').mockResolvedValue({ enabled: true, provider: 'Test AI', max_documents: 20, max_pages: 100, max_pages_per_document: 30 })
  vi.spyOn(caseAiApi, 'materials').mockResolvedValue({ items: [{ id: 'record', title: 'Synthetic record', clinical_summary: '', record_type: 'other', event_date: '2026-10-11', status: 'unconfirmed' }], total: 1 })
  vi.spyOn(caseAiApi, 'latest').mockResolvedValue(null)
})
afterEach(() => { vi.restoreAllMocks() })
const lost = vi.fn().mockResolvedValue(undefined)

it('requires explicit selection and consent before sending documents', async () => {
  const start = vi.spyOn(caseAiApi, 'start').mockResolvedValue({ ...completed, status: 'queued' })
  render(<CaseAiSummary c={c} onOpen={vi.fn()} onAccessLost={lost} />)
  await screen.findByText('2026-10-11 · Synthetic record')
  const button = screen.getByRole('button', { name: 'Подготовить сводку' })
  expect(button).toBeDisabled()
  const boxes = screen.getAllByRole('checkbox')
  expect(boxes[1]).not.toBeChecked()
  fireEvent.click(boxes[0]); expect(button).toBeDisabled()
  fireEvent.click(boxes[1]); fireEvent.click(button)
  await waitFor(() => expect(start).toHaveBeenCalledWith('case', ['record'], 3, expect.any(String), expect.any(AbortSignal)))
  expect(await screen.findByRole('button', { name: 'Остановить анализ' })).toBeEnabled()
})

it('opens the exact source page and restores the saved result', async () => {
  vi.mocked(caseAiApi.latest).mockResolvedValue(completed)
  const open = vi.fn()
  render(<CaseAiSummary c={c} onOpen={open} onAccessLost={lost} />)
  fireEvent.click(await screen.findByText('Стр. 2: «Original finding»'))
  expect(open).toHaveBeenCalledWith('record', 'file', 2)
  expect(screen.getByText('Synthetic finding')).toBeVisible()
})

it('clears facts on focus when access has been revoked', async () => {
  vi.mocked(caseAiApi.latest).mockResolvedValueOnce(completed).mockRejectedValue(new Error('Access lost'))
  render(<CaseAiSummary c={c} onOpen={vi.fn()} onAccessLost={lost} />)
  await screen.findByText('Synthetic finding')
  act(() => window.dispatchEvent(new Event('focus')))
  await screen.findByRole('alert')
  expect(screen.queryByText('Synthetic finding')).not.toBeInTheDocument()
  expect(lost).toHaveBeenCalled()
})

it('lets the doctor choose new materials after a stale result conflict', async () => {
  const error = new AxiosError('stale')
  error.response = { status: 409, data: { detail: 'Материалы изменились' } } as typeof error.response
  vi.mocked(caseAiApi.latest).mockRejectedValue(error)
  render(<CaseAiSummary c={c} onOpen={vi.fn()} onAccessLost={lost} />)
  await screen.findByText('2026-10-11 · Synthetic record')
  expect(screen.getByRole('alert')).toHaveTextContent('Материалы изменились')
  fireEvent.click(screen.getAllByRole('checkbox')[0]); fireEvent.click(screen.getAllByRole('checkbox')[1])
  expect(screen.getByRole('button', { name: 'Подготовить сводку' })).toBeEnabled()
})

it('aborts outstanding requests when the workspace is closed', async () => {
  let signal: AbortSignal | undefined
  vi.mocked(caseAiApi.latest).mockImplementation(async (_, next) => { signal = next; return completed })
  const view = render(<CaseAiSummary c={c} onOpen={vi.fn()} onAccessLost={lost} />)
  await screen.findByText('Synthetic finding')
  view.unmount(); expect(signal?.aborted).toBe(true)
})
