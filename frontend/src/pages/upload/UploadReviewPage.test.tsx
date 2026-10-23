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
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); useUploadStore.setState(initialUploads, true); usePatientsStore.setState(initialPatients, true) })

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

it('opens the original, returns to fields and preserves edits after closing', async () => {
  const api = (await import('../../api/api')).default
  const job: UploadJob = {
    id: 'job', status: 'needs_review', original_filename: 'scan.png', archive_storage_key: null,
    size_bytes: 42, created_at: '', finished_at: null, review_updated_at: null, review_decisions: [],
    report_json: { patients: [{ candidate_id: 'patient', fio: 'Тестовый пациент', date_of_birth: null,
      sources: [], existing_matches: [], record_groups: [{ group_id: 'group', title: 'Исследование',
        record_type: 'other', event_date: '2026-01-01', event_date_candidates: [], payload_json: {},
        duplicate_candidates: [], files: [{ id: 'scan', filename: 'scan.png', path: 'scan.png',
          size_bytes: 42, mime_type: 'image/png', is_dicom: false }] }] }] },
  }
  vi.spyOn(api, 'get').mockImplementation(async url => String(url).endsWith('/files/scan')
    ? { data: new Blob(['synthetic image']), headers: { 'content-type': 'image/png' } }
    : { data: job })
  const revoke = vi.fn()
  vi.stubGlobal('URL', class extends URL {
    static createObjectURL = vi.fn(() => 'blob:synthetic')
    static revokeObjectURL = revoke
  })
  useUploadStore.setState({ currentJob: job, getJobById: vi.fn(), saveReviewDraft: vi.fn().mockResolvedValue(null) })
  usePatientsStore.setState({ patients: [], fetchPatients: vi.fn() })
  render(<MemoryRouter initialEntries={['/upload/review/job']}><Routes><Route path="/upload/review/:jobId" element={<UploadReviewPage />} /></Routes></MemoryRouter>)
  fireEvent.change(await screen.findByLabelText('Название'), { target: { value: 'Правка врача' } })
  const open = screen.getByRole('button', { name: 'Открыть документ scan.png' })
  open.focus()
  fireEvent.click(open)
  expect(screen.getByLabelText('Сверка с исходным документом')).toHaveFocus()
  expect(await screen.findByRole('heading', { name: 'scan.png' })).toBeVisible()
  await screen.findByRole('img', { name: 'Вложение медицинской записи' })
  expect(api.get).toHaveBeenCalledWith('/archives/imports/job/files/scan', expect.objectContaining({ responseType: 'blob' }))
  fireEvent.click(screen.getByRole('button', { name: 'Вернуться к полям записи' }))
  expect(screen.getByRole('button', { name: 'Поля записи' })).toHaveAttribute('aria-pressed', 'true')
  expect(open).toHaveFocus()
  expect(screen.getByLabelText('Название')).toHaveValue('Правка врача')
  fireEvent.click(screen.getByRole('button', { name: 'Документ' }))
  fireEvent.click(screen.getByRole('button', { name: 'Закрыть просмотр' }))
  expect(screen.queryByLabelText('Сверка с исходным документом')).not.toBeInTheDocument()
  expect(screen.getByLabelText('Название')).toHaveValue('Правка врача')
  expect(open).toHaveFocus()
  expect(revoke).toHaveBeenCalledWith('blob:synthetic')
})
