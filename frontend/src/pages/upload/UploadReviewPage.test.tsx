import { AxiosError } from 'axios'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
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
  fireEvent.click(await screen.findByRole('button', { name: 'Сохранить 1 записей в историю' }))
  await screen.findByText('Сервер обнаружил дубль при окончательной проверке. Сравните запись с историей перед подтверждением.')
  expect(screen.getByText('Нужны данные: 1 документов')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить 1 записей в историю' }))
  expect(resolve).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('button', { name: 'Импортировать всё равно' }))
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить 1 записей в историю' }))
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
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить 1 записей в историю' }))
  await screen.findByRole('button', { name: 'Сохранить 1 записей в историю' })
  expect(screen.getByLabelText('Название')).toHaveValue('Ручная правка')
  expect(screen.getByLabelText('Карточка пациента')).toHaveValue('context')
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить 1 записей в историю' }))
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

function demoJob(secondDate: string | null = '2026-01-02'): UploadJob {
  return {
    id: 'job', status: 'needs_review', original_filename: 'documents.zip', archive_storage_key: null,
    size_bytes: 42, created_at: '', finished_at: null, review_updated_at: null, review_decisions: [],
    report_json: { patients: ['first', 'second'].map((id, index) => ({
      candidate_id: id, fio: `Пациент ${index + 1}`, date_of_birth: null, sources: [], existing_matches: [],
      record_groups: [{ group_id: `group-${id}`, title: `Документ ${index + 1}`, record_type: 'other',
        event_date: index === 0 ? '2026-01-01' : secondDate, event_date_candidates: [], payload_json: {},
        files: [], duplicate_candidates: [] }],
    })) },
  }
}

function NavigationProbe() {
  const location = useLocation()
  const navigate = useNavigate()
  return <><output aria-label="Адрес экрана">{location.search}</output><button onClick={() => navigate(-1)}>Назад в браузере</button></>
}

function renderReview(job: UploadJob, query = '') {
  const save = vi.fn().mockResolvedValue('2026-10-23T12:00:00Z')
  const resolve = vi.fn().mockResolvedValue(undefined)
  useUploadStore.setState({ currentJob: job, getJobById: vi.fn(), resolveJob: resolve, saveReviewDraft: save })
  usePatientsStore.setState({ patients: [], fetchPatients: vi.fn() })
  render(<MemoryRouter initialEntries={[`/upload/review/job${query}`]}><Routes>
    <Route path="/upload/review/:jobId" element={<><UploadReviewPage /><NavigationProbe /></>} />
    <Route path="/upload/status/:jobId" element={<p>Импорт завершён</p>} />
  </Routes></MemoryRouter>)
  return { save, resolve }
}

it('keeps every document draft when switching, going back and autosaving', async () => {
  const { save } = renderReview(demoJob())
  fireEvent.change(await screen.findByLabelText('Название'), { target: { value: 'Правка первого' } })
  fireEvent.change(screen.getByLabelText('Клиническое описание'), { target: { value: 'Описание первого' } })
  const list = screen.getByRole('navigation', { name: 'Документы импорта' })
  fireEvent.click(within(list).getByRole('button', { name: /2\. Документ 2/ }))
  expect(screen.getAllByLabelText('Название')).toHaveLength(1)
  expect(screen.getByLabelText('Название')).toHaveValue('Документ 2')
  expect(screen.getByLabelText('Адрес экрана')).toHaveTextContent('group=group-second')
  fireEvent.change(screen.getByLabelText('Название'), { target: { value: 'Правка второго' } })
  fireEvent.click(screen.getByRole('button', { name: 'Назад в браузере' }))
  expect(screen.getByLabelText('Название')).toHaveValue('Правка первого')
  expect(screen.getByLabelText('Клиническое описание')).toHaveValue('Описание первого')
  await waitFor(() => expect(save).toHaveBeenCalled(), { timeout: 2000 })
  const payload = save.mock.calls[save.mock.calls.length - 1]?.[1]
  expect(payload[0].record_groups[0]).toMatchObject({ title: 'Правка первого', clinical_summary: 'Описание первого' })
  expect(payload[1].record_groups[0]).toMatchObject({ title: 'Правка второго' })
})

it('excludes every record of a skipped patient from totals and confirmation', async () => {
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
  const { resolve } = renderReview(demoJob())
  fireEvent.change(await screen.findByLabelText('Решение'), { target: { value: 'skip' } })
  expect(screen.getByText('Можно сохранить: 1 записей')).toBeVisible()
  expect(screen.getByText('Пропущено: 1 документов')).toBeVisible()
  expect(screen.getByText('Нужны данные: 0 документов')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить 1 записей в историю' }))
  await screen.findByText('Импорт завершён')
  expect(confirm).toHaveBeenCalledWith('Подтвердить импорт: пациентов — 1, записей — 1?')
  expect(resolve.mock.calls[0][1][0]).toMatchObject({ action: 'skip' })
})

it('opens the missing-date document before asking the doctor to resolve it', async () => {
  const { resolve } = renderReview(demoJob(null))
  await screen.findByLabelText('Название')
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить 2 записей в историю' }))
  expect(await screen.findByText('Укажите дату события для каждой импортируемой медицинской записи.')).toBeVisible()
  expect(screen.getByLabelText('Название')).toHaveValue('Документ 2')
  expect(screen.getByLabelText('Дата события')).toHaveValue('')
  expect(resolve).not.toHaveBeenCalled()
})

it('keeps the selected group and edited values after moving it to another patient', async () => {
  const job = demoJob()
  const api = (await import('../../api/api')).default
  const put = vi.spyOn(api, 'put').mockImplementation(async (_url, body) => {
    const request = body as { decisions: UploadJob['review_decisions'] }
    const updated = structuredClone(job)
    const patients = updated.report_json.patients!
    patients[0].record_groups.push(patients[1].record_groups[0])
    patients.splice(1, 1)
    updated.review_decisions = [{ ...request.decisions[0], record_groups: [...request.decisions[0].record_groups, ...request.decisions[1].record_groups] }]
    return { data: updated }
  })
  renderReview(job, '?group=group-second')
  fireEvent.change(await screen.findByLabelText('Название'), { target: { value: 'Документ после сверки' } })
  fireEvent.change(screen.getByLabelText('Пациент этого документа'), { target: { value: 'first' } })
  await waitFor(() => expect(screen.getByLabelText('ФИО')).toHaveValue('Пациент 1'))
  expect(put).toHaveBeenCalledWith('/archives/imports/job/groups', expect.objectContaining({ group_id: 'group-second', target_candidate_id: 'first' }))
  expect(screen.getByLabelText('Название')).toHaveValue('Документ после сверки')
  expect(screen.getByLabelText('Адрес экрана')).toHaveTextContent('group=group-second')
  expect(within(screen.getByRole('navigation', { name: 'Документы импорта' })).getByRole('button', { name: /2\. Документ после сверки/ })).toHaveAttribute('aria-current', 'true')
})


it('can finish an entirely skipped import with an explicit zero-record confirmation', async () => {
  const job = demoJob()
  job.report_json.patients = job.report_json.patients!.slice(0, 1)
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
  const { resolve } = renderReview(job)
  fireEvent.change(await screen.findByLabelText('Решение'), { target: { value: 'skip' } })
  fireEvent.click(screen.getByRole('button', { name: 'Завершить без создания записей' }))
  await screen.findByText('Импорт завершён')
  expect(confirm).toHaveBeenCalledWith('Завершить импорт без создания записей? Все документы будут пропущены.')
  expect(resolve).toHaveBeenCalledWith('job', [expect.objectContaining({ action: 'skip' })])
})

it.each([
  ['Название', 'Уточнённое название', 'title', 'Уточнённое название'],
  ['Дата события', '03.01.2026', 'event_date', '2026-01-03'],
  ['Тип', 'lab_result', 'record_type', 'lab_result'],
  ['ФИО', 'Уточнённый пациент', null, null],
])('rechecks server duplicates after changing %s without overriding the old finding', async (label, input, field, expected) => {
  const { resolve } = renderReview(demoJob())
  const failure = new AxiosError('duplicate')
  failure.response = { status: 422, data: { detail: { code: 'duplicate_confirmation_required', group_id: 'group-first' } },
    statusText: '', headers: {}, config: { headers: {} } } as AxiosError['response']
  resolve.mockRejectedValueOnce(failure)
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  fireEvent.click(await screen.findByRole('button', { name: 'Сохранить 2 записей в историю' }))
  await screen.findByText('Сервер обнаружил дубль при окончательной проверке. Сравните запись с историей перед подтверждением.')
  fireEvent.change(screen.getByLabelText(label!), { target: { value: input } })
  expect(screen.queryByRole('button', { name: 'Импортировать всё равно' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить 2 записей в историю' }))
  await screen.findByText('Импорт завершён')
  expect(resolve).toHaveBeenCalledTimes(2)
  const patient = resolve.mock.calls[1][1][0]
  expect(patient.record_groups[0].allow_possible_duplicate).toBe(false)
  if (field) expect(patient.record_groups[0][field]).toBe(expected)
  else expect(patient.fio).toBe(input)
})
