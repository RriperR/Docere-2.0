import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { useUploadStore, UploadJob } from '../../stores/uploadStore'
import { usePatientsStore } from '../../stores/patientsStore'
import UploadReviewPage from './UploadReviewPage'

vi.mock('../../components/records/DocumentViewer', () => ({ default: () => null }))
vi.mock('./useImportAi', () => ({ useImportAi: () => ({ capabilities: { enabled: true }, active: false, busy: false, history: [],
  run: { id: 'run', provider: 'Test', model: 'Test', documents: [{ file_id: 'file', filename: 'scan.png', status: 'completed', result: { fields: {
    fio: { value: 'Тестовый пациент', sources: [{ page: 1, excerpt: 'Пациент' }] },
    event_date: { value: '2026-10-11', sources: [{ page: 1, excerpt: '11.10.2026' }] },
    clinical_summary: { value: 'Сведения из оригинала', sources: [{ page: 1, excerpt: 'Обследование' }] },
  } } }] } }) }))
const uploads = useUploadStore.getState(), patients = usePatientsStore.getState()
afterEach(() => { cleanup(); vi.restoreAllMocks(); useUploadStore.setState(uploads, true); usePatientsStore.setState(patients, true) })
it('keeps all references when filling several empty fields and preserves manual edits', async () => {
  const job: UploadJob = { id: 'job', status: 'needs_review', version: 2, original_filename: 'documents.zip', archive_storage_key: null, size_bytes: 2, created_at: '', finished_at: null, review_updated_at: null, review_decisions: [],
    report_json: { patients: [{ candidate_id: 'patient', fio: null, date_of_birth: null, sources: [], existing_matches: [], record_groups: [{ group_id: 'group', title: 'Ручное название', event_date: null, event_date_candidates: [], record_type: 'other', payload_json: {}, duplicate_candidates: [], files: [{ id: 'file', path: 'scan.png', filename: 'scan.png', size_bytes: 2, mime_type: 'image/png', is_dicom: false }] }] }] } }
  const save = vi.fn().mockResolvedValue(null)
  useUploadStore.setState({ currentJob: job, getJobById: vi.fn(), saveReviewDraft: save })
  usePatientsStore.setState({ patients: [], fetchPatients: vi.fn() })
  render(<MemoryRouter initialEntries={['/upload/review/job']}><Routes><Route path="/upload/review/:jobId" element={<UploadReviewPage />} /></Routes></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: 'Заполнить пустые поля' }))
  expect(screen.getByLabelText('Клиническое описание')).toHaveValue('Сведения из оригинала')
  fireEvent.change(screen.getByLabelText('Клиническое описание'), { target: { value: 'Исправлено врачом' } })
  fireEvent.click(screen.getByRole('button', { name: 'Заполнить пустые поля' }))
  expect(screen.getByLabelText('Клиническое описание')).toHaveValue('Исправлено врачом')
  const replace = screen.getByRole('button', { name: 'Заменить: Клиническое описание' })
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
  fireEvent.click(replace)
  expect(confirm).toHaveBeenCalledWith('Заменить введённое значение предложением AI?')
  expect(screen.getByLabelText('Клиническое описание')).toHaveValue('Исправлено врачом')
  confirm.mockReturnValue(true)
  fireEvent.click(replace)
  expect(screen.getByLabelText('Клиническое описание')).toHaveValue('Сведения из оригинала')
  await waitFor(() => expect(save).toHaveBeenCalled(), { timeout: 2000 })
  const group = save.mock.calls[save.mock.calls.length - 1][1][0].record_groups[0]
  expect(group.title).toBe('Ручное название')
  expect(group.applied_ai.flatMap((reference: { fields: string[] }) => reference.fields).sort()).toEqual(['clinical_summary', 'event_date', 'fio'])
})
