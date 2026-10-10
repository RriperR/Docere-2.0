import { AxiosError } from 'axios'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { useUploadStore, type UploadJob } from '../../stores/uploadStore'
import { usePatientsStore } from '../../stores/patientsStore'
import UploadReviewPage from './UploadReviewPage'

const initialUploads = useUploadStore.getState()
const initialPatients = usePatientsStore.getState()
afterEach(() => { cleanup(); vi.restoreAllMocks(); useUploadStore.setState(initialUploads, true); usePatientsStore.setState(initialPatients, true) })

it('lets the doctor explicitly confirm a duplicate found only during final validation', async () => {
  const job: UploadJob = { id: 'job', status: 'needs_review', original_filename: 'demo.zip', archive_storage_key: null,
    size_bytes: 42, created_at: '', finished_at: null, review_updated_at: null, review_decisions: [], report_json: {
      patients: [{ candidate_id: 'patient', fio: 'Тестовый пациент', date_of_birth: null, sources: [], existing_matches: [],
        record_groups: [{ group_id: 'group', title: 'Исследование', record_type: 'other', event_date: '2026-01-01',
          event_date_candidates: [], payload_json: {}, files: [], duplicate_candidates: [] }] }],
    } }
  const failure = new AxiosError('duplicate')
  failure.response = { status: 422, data: { detail: { code: 'duplicate_confirmation_required', group_id: 'group' } }, statusText: '', headers: {}, config: { headers: {} } } as AxiosError['response']
  const resolve = vi.fn().mockRejectedValueOnce(failure).mockResolvedValueOnce(undefined)
  useUploadStore.setState({ currentJob: job, getJobById: vi.fn(), resolveJob: resolve, saveReviewDraft: vi.fn().mockResolvedValue(null) })
  usePatientsStore.setState({ patients: [], fetchPatients: vi.fn() })
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  render(<MemoryRouter initialEntries={['/upload/review/job']}><Routes>
    <Route path="/upload/review/:jobId" element={<UploadReviewPage />} />
    <Route path="/upload/status/:jobId" element={<p>Импорт завершён</p>} />
  </Routes></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: 'Подтвердить импорт' }))
  await screen.findByText('Сервер обнаружил дубль при окончательной проверке. Сравните запись с историей перед подтверждением.')
  expect(screen.getByText('Требуют решения: 1')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Подтвердить импорт' }))
  expect(resolve).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('button', { name: 'Импортировать всё равно' }))
  fireEvent.click(screen.getByRole('button', { name: 'Подтвердить импорт' }))
  await screen.findByText('Импорт завершён')
  expect(resolve).toHaveBeenCalledTimes(2)
  expect(resolve.mock.calls[1][1][0].record_groups[0].allow_possible_duplicate).toBe(true)
})
