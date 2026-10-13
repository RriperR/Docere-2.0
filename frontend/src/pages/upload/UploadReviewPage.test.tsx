import { AxiosError } from 'axios'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { useUploadStore, type UploadJob } from '../../stores/uploadStore'
import { usePatientsStore } from '../../stores/patientsStore'
import UploadReviewPage from './UploadReviewPage'

vi.mock('./useImportAi', () => ({ useImportAi: () => ({ capabilities: { enabled: false }, active: false, busy: false, history: [] }) }))

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

it('uses a server-verified patient only after explicit choice and retains review after network failure', async () => {
  const api = (await import('../../api/api')).default
  vi.spyOn(api, 'get').mockImplementation(async url => ({ data: String(url) === '/patients/context' ? { id: 'context', fio: 'Карточка контекста', date_of_birth: '1980-05-05' } : { enabled: false } }))
  const job: UploadJob = { id: 'job', status: 'needs_review', original_filename: 'scan.png', archive_storage_key: null, size_bytes: 42, created_at: '', finished_at: null, review_updated_at: null, review_decisions: [], report_json: { patients: [{ candidate_id: 'candidate', fio: 'Другое имя в документе', date_of_birth: '1990-01-01', sources: [], existing_matches: [], record_groups: [{ group_id: 'group', title: 'Документ', record_type: 'other', event_date: '2026-10-13', event_date_candidates: [], payload_json: {}, files: [], duplicate_candidates: [] }] }] } }
  const resolve = vi.fn().mockRejectedValueOnce(Error('network')).mockResolvedValueOnce(undefined)
  useUploadStore.setState({ currentJob: job, getJobById: vi.fn(), resolveJob: resolve, saveReviewDraft: vi.fn().mockResolvedValue(null) })
  usePatientsStore.setState({ patients: [], fetchPatients: vi.fn(), error: null })
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  render(<MemoryRouter initialEntries={['/upload/review/job?patient=context']}><Routes><Route path="/upload/review/:jobId" element={<UploadReviewPage />} /><Route path="/upload/status/:jobId" element={<p>Готово</p>} /></Routes></MemoryRouter>)
  const choose = await screen.findByRole('button', { name: 'Выбрать Карточка контекста для этих документов' })
  expect(screen.getByLabelText('Решение')).toHaveValue('create')
  expect(screen.getByLabelText('Дата рождения')).toHaveValue('01.01.1990')
  expect(screen.getByText(/при несовпадении выберите другую карточку/)).toBeVisible()
  fireEvent.click(choose)
  expect(screen.getByLabelText('Карточка пациента')).toHaveValue('context')
  fireEvent.change(screen.getByLabelText('Название'), { target: { value: 'Ручная правка' } })
  fireEvent.click(screen.getByRole('button', { name: 'Подтвердить импорт' }))
  await screen.findByRole('button', { name: 'Подтвердить импорт' })
  expect(screen.getByLabelText('Название')).toHaveValue('Ручная правка')
  expect(screen.getByLabelText('Карточка пациента')).toHaveValue('context')
  fireEvent.click(screen.getByRole('button', { name: 'Подтвердить импорт' }))
  await screen.findByText('Готово')
  expect(resolve.mock.calls[1][1][0].record_groups[0]).toMatchObject({ title: 'Ручная правка', event_date: '2026-10-13' })
})
