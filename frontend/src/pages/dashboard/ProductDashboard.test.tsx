import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import api from '../../api/api'
import { caseApi, type CaseView, type Page } from '../../api/cases'
import { useAuthStore } from '../../stores/authStore'
import { usePatientsStore } from '../../stores/patientsStore'
import { useUploadStore } from '../../stores/uploadStore'
import { useInboxStore } from '../../stores/inboxStore'
import DoctorDashboard from './DoctorDashboard'
import DashboardInbox from './DashboardInbox'
import RecentCases from './RecentCases'

const ownPatient = { id: 'own', fio: 'Врач Синтетический', date_of_birth: null, email: null, phone: null, status: 'confirmed', access_context: 'own_confirmed', record_count: 0, last_record_date: null }
const task = { key: 'review-import', kind: 'import_review', id: 'import', case_id: null, actor_name: null, context: 'Материалы.zip', created_at: '2026-10-13T10:00:00Z' }
const clinicalTask = { ...task, key: 'opinion', kind: 'opinion_requested', id: 'opinion', case_id: 'previous-case', context: 'Клинический контекст предыдущего пациента' }
const activeCase = (id: string, unread: number): CaseView => ({ id, status: 'active', membership_status: 'accepted', coordinator_id: 'doctor', coordinator_name: 'Координатор', management_members: [], unread_messages: unread, patient_name: 'Синтетический Пациент', material_count: 1, accessible: true, invitation_terms: '', case: { id, patient_id: 'patient', coordinator_id: 'doctor', title: `Разбор ${id}`, question: 'Вопрос для коллеги', status: 'active', version: 1, sequence: 1, record_ids: [], members: [], created_at: '2026-10-13', previous_case_id: null, published_record_id: null } })
const mount = (element: React.ReactNode) => render(<MemoryRouter>{element}</MemoryRouter>)

beforeEach(() => {
  useAuthStore.setState({ user: { id: 'doctor', fio: ownPatient.fio, first_name: 'Врач', last_name: 'Синтетический', middle_name: null, birthday: null, date_of_birth: null, email: 'doctor@example.com', phone: '', role: 'doctor', status: 'active', specialty: null, photo: null, username: '' } })
  usePatientsStore.setState({ patients: [], error: null })
  useUploadStore.setState({ jobs: [], error: null })
  useInboxStore.setState({ revision: 0 })
  vi.spyOn(api, 'get').mockImplementation(async url => ({ data: url === '/patients' ? [ownPatient] : url === '/cases' || url === '/inbox/tasks' ? { items: [], total: 0 } : [] }))
})
afterEach(() => vi.restoreAllMocks())

it('keeps onboarding focused on adding a patient even when the own card already exists', async () => {
  mount(<DoctorDashboard />)
  await screen.findByRole('heading', { name: 'Первый разбор за три шага' })
  expect(screen.getByRole('link', { name: 'Добавить пациента' })).toHaveAttribute('href', '/patients?create=1')
  expect(screen.queryByRole('link', { name: 'Создать случай' })).not.toBeInTheDocument()
  expect(screen.getByText('Ваша карточка')).toBeInTheDocument()
})

it('shows an import review once in the unified inbox and preserves failed import follow-up', async () => {
  vi.mocked(api.get).mockImplementation(async url => ({ data: url === '/patients' ? [ownPatient] : url === '/cases' ? { items: [], total: 0 } : url === '/inbox/tasks' ? { items: [task], total: 7 } : url === '/archives/imports' ? [{ id: 'import', status: 'needs_review', original_filename: 'Материалы.zip' }, { id: 'failed', status: 'failed', original_filename: 'Ошибка.zip' }] : [] }))
  mount(<DoctorDashboard />)
  expect(await screen.findByRole('link', { name: /Проверить материалы/ })).toHaveAttribute('href', '/upload/review/import')
  expect(screen.getAllByText('Материалы.zip')).toHaveLength(1)
  expect(await screen.findByRole('link', { name: /Разобрать ошибку импорта/ })).toHaveAttribute('href', '/upload/status/failed')
  expect(screen.getByLabelText('Всего задач: 7')).toHaveTextContent('7')
})

it('does not claim the inbox is empty after failure and retries with the keyboard', async () => {
  vi.mocked(api.get).mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ data: { items: [task], total: 1 } })
  mount(<DashboardInbox />)
  expect(screen.getByRole('status')).toBeInTheDocument()
  expect(screen.queryByText('Всё разобрано')).not.toBeInTheDocument()
  await screen.findByRole('alert')
  expect(screen.queryByText('Всё разобрано')).not.toBeInTheDocument()
  const user = userEvent.setup()
  await user.tab()
  expect(screen.getByRole('button', { name: 'Повторить загрузку входящих' })).toHaveFocus()
  await user.keyboard('{Enter}')
  await screen.findByRole('link', { name: /Проверить материалы/ })
})

it('ignores the previous inbox response when refreshed', async () => {
  const reads: Array<(response: unknown) => void> = []
  vi.mocked(api.get).mockImplementation(() => new Promise(resolve => reads.push(resolve)))
  mount(<DashboardInbox />)
  act(() => useInboxStore.setState({ revision: 1 }))
  await act(async () => reads[1]({ data: { items: [], total: 0 } }))
  expect(screen.getByText('Всё разобрано')).toBeInTheDocument()
  await act(async () => reads[0]({ data: { items: [task], total: 1 } }))
  expect(screen.queryByText('Материалы.zip')).not.toBeInTheDocument()
})

it('prioritizes cases with new messages while keeping inaccessible invitations neutral', async () => {
  const invitation = { ...activeCase('invitation', 8), membership_status: 'pending', accessible: false }
  vi.spyOn(caseApi, 'list').mockResolvedValue({ items: [activeCase('old', 0), activeCase('new', 3), invitation], total: 3 })
  mount(<RecentCases />)
  await screen.findByText('Приглашение в разбор')
  const section = screen.getByRole('region', { name: 'Продолжить разбор' })
  const links = within(section).getAllByRole('link')
  expect(links[1]).toHaveAttribute('href', '/cases/invitation')
  expect(links[1]).not.toHaveTextContent('Вопрос для коллеги')
  expect(links[1]).not.toHaveTextContent('Синтетический Пациент')
  expect(links[2]).toHaveAttribute('href', '/cases/new')
  expect(screen.queryByText('Разбор old')).not.toBeInTheDocument()
})

it('keeps case loading and retry distinct from the empty state', async () => {
  const reads: Array<(page: Page<CaseView>) => void> = []
  vi.spyOn(caseApi, 'list').mockRejectedValueOnce(new Error('offline')).mockImplementation(() => new Promise(resolve => reads.push(resolve)))
  mount(<RecentCases />)
  await screen.findByRole('alert')
  expect(screen.queryByText('Начните совместный разбор')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
  expect(screen.getByRole('status')).toBeInTheDocument()
  await act(async () => reads[0]({ items: [], total: 0 }))
  expect(screen.getByText('Начните совместный разбор')).toBeInTheDocument()
})

it('conceals the old context while refreshing an access revocation', async () => {
  let finish: (response: unknown) => void = () => {}
  vi.mocked(api.get).mockResolvedValueOnce({ data: { items: [clinicalTask], total: 1 } }).mockImplementation(() => new Promise(resolve => { finish = resolve }))
  mount(<DashboardInbox />)
  await screen.findByRole('link', { name: 'Ответить коллеге' })
  act(() => useInboxStore.setState({ revision: 1 }))
  expect(screen.queryByRole('link', { name: 'Ответить коллеге' })).not.toBeInTheDocument()
  expect(screen.queryByText('Клинический контекст предыдущего пациента')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Всего задач: 1')).not.toBeInTheDocument()
  expect(screen.getByRole('status')).toBeVisible()
  expect(screen.getByRole('region', { name: 'Входящие задачи' })).toHaveAttribute('aria-busy', 'true')
  await act(async () => finish({ data: { items: [], total: 0 } }))
  expect(screen.getByText('Всё разобрано')).toBeVisible()
  expect(screen.queryByRole('link', { name: 'Ответить коллеге' })).not.toBeInTheDocument()
})


it('requests and displays the first five inbox tasks with the full server count', async () => {
  const tasks = Array.from({ length: 5 }, (_, index) => ({ ...task, key: `task-${index}`, id: `import-${index}`, context: `Материалы-${index}.zip` }))
  vi.mocked(api.get).mockResolvedValue({ data: { items: tasks, total: 8 } })
  mount(<DashboardInbox />)
  expect(await screen.findAllByRole('link', { name: 'Проверить материалы' })).toHaveLength(5)
  expect(api.get).toHaveBeenCalledWith('/inbox/tasks', expect.objectContaining({ params: { offset: 0, limit: 5 } }))
  expect(screen.getByLabelText('Всего задач: 8')).toHaveTextContent('8')
})

it('clears account context on logout, hides it for another account and ignores the old response', async () => {
  const reads: Array<(response: unknown) => void> = []
  vi.mocked(api.get).mockResolvedValueOnce({ data: { items: [clinicalTask], total: 1 } }).mockImplementation(() => new Promise(resolve => reads.push(resolve)))
  mount(<DashboardInbox />)
  await screen.findByRole('link', { name: 'Ответить коллеге' })
  act(() => useInboxStore.setState({ revision: 1 }))
  const previousUser = useAuthStore.getState().user!
  act(() => useAuthStore.setState({ user: null }))
  expect(screen.queryByText('Клинический контекст предыдущего пациента')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Всего задач: 1')).not.toBeInTheDocument()
  expect(screen.getByText('Входящие доступны после входа в аккаунт.')).toBeInTheDocument()
  expect(api.get).toHaveBeenCalledTimes(2)
  act(() => useAuthStore.setState({ user: { ...previousUser, id: 'another-doctor' } }))
  expect(screen.getByRole('status')).toBeVisible()
  await act(async () => reads[1]({ data: { items: [], total: 0 } }))
  expect(screen.getByText('Всё разобрано')).toBeVisible()
  await act(async () => reads[0]({ data: { items: [clinicalTask], total: 1 } }))
  expect(screen.queryByText('Клинический контекст предыдущего пациента')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Всего задач: 1')).not.toBeInTheDocument()
})

it('hides the loaded context immediately when switching accounts without remounting', async () => {
  let finish: (response: unknown) => void = () => {}
  vi.mocked(api.get).mockResolvedValueOnce({ data: { items: [clinicalTask], total: 1 } }).mockImplementation(() => new Promise(resolve => { finish = resolve }))
  mount(<DashboardInbox />)
  await screen.findByRole('link', { name: 'Ответить коллеге' })
  act(() => useAuthStore.setState({ user: { ...useAuthStore.getState().user!, id: 'another-doctor' } }))
  expect(screen.queryByText('Клинический контекст предыдущего пациента')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Всего задач: 1')).not.toBeInTheDocument()
  expect(screen.getByRole('status')).toBeVisible()
  await act(async () => finish({ data: { items: [], total: 0 } }))
  expect(screen.getByText('Всё разобрано')).toBeVisible()
})
