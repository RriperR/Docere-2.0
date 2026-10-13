import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import api from '../../api/api'
import { useAuthStore } from '../../stores/authStore'
import { usePatientsStore } from '../../stores/patientsStore'
import { useDoctorRoleApplicationsStore, type DoctorRoleApplication } from '../../stores/doctorRoleApplicationsStore'
import { useUploadStore } from '../../stores/uploadStore'
import { useShareRequestsStore } from '../../stores/shareRequestsStore'
import DoctorRoleStatus from '../roles/DoctorRoleStatus'
import DoctorRequestPage from '../roles/DoctorRequestPage'
import DoctorDashboard from './DoctorDashboard'
import PatientDashboard from './PatientDashboard'
import PatientListPage from '../patients/PatientListPage'

const patient = { id: 'own', fio: 'Синтетический Пациент', date_of_birth: null, email: null, phone: null, status: 'confirmed', access_context: 'own_confirmed', record_count: 0, last_record_date: null }
const application = (status: DoctorRoleApplication['status']): DoctorRoleApplication => ({ id: 'application', applicant_user_id: 'user', applicant_fio: 'Синтетический Пациент', applicant_email: 'synthetic@example.com', applicant_date_of_birth: null, specialty: 'Кардиология', status, created_at: '2026-10-12T10:00:00Z', resolved_at: null, reviews: [{ id: 'review', reviewer_user_id: 'admin', reviewer_fio: 'Администратор', reviewer_email: 'admin@example.com', reviewer_role: 'admin', reviewer_specialty: null, status: status === 'pending' ? 'pending' : status, note: status === 'rejected' ? 'Уточните специализацию' : null, created_at: '2026-10-12T10:00:00Z', responded_at: null }] })
function mount(element: React.ReactNode, url = '/dashboard') { return render(<MemoryRouter initialEntries={[url]}>{element}</MemoryRouter>) }
beforeEach(() => {
  useAuthStore.setState({ user: { id: 'user', fio: patient.fio, first_name: 'Пациент', last_name: 'Синтетический', middle_name: null, birthday: null, date_of_birth: null, email: 'synthetic@example.com', phone: '', role: 'patient', status: 'active', specialty: null, photo: null, username: '' }, refreshUser: vi.fn().mockResolvedValue(undefined) })
  usePatientsStore.setState({ patients: [], filteredPatients: [], currentPatient: null, patientRecords: [], error: null })
  useDoctorRoleApplicationsStore.setState({ mine: [], reviewers: [], specialties: [], error: null, isLoading: false })
  useUploadStore.setState({ jobs: [], error: null })
  useShareRequestsStore.setState({ inbox: [], error: null })
  vi.spyOn(api, 'get').mockImplementation(async url => {
    if (url === '/patients') return { data: [patient] }
    if (String(url).endsWith('/records')) return { data: [] }
    if (url === '/inbox/tasks' || url === '/cases') return { data: { items: [], total: 0 } }
    return { data: [] }
  })
})
afterEach(() => vi.restoreAllMocks())

it('shows the own history and a separate doctor application action without exposing doctor actions', async () => {
  mount(<PatientDashboard />)
  expect(screen.getByText('Загружаем вашу историю…')).toBeInTheDocument()
  await screen.findByRole('link', { name: 'Я врач' })
  await screen.findByText('Ваши медицинские записи появятся здесь')
  expect(screen.getByRole('link', { name: 'Открыть карточку' })).toHaveAttribute('href', '/patients/own')
  expect(screen.queryByText('Добавить пациента')).not.toBeInTheDocument()
})
it.each(['pending', 'rejected', 'approved'] as const)('shows %s on the dashboard', async status => {
  vi.mocked(api.get).mockResolvedValue({ data: [application(status)] })
  mount(<DoctorRoleStatus />)
  await screen.findByText(status === 'pending' ? 'Заявка на роль врача на проверке' : status === 'rejected' ? 'Заявка на роль врача отклонена' : 'Заявка на роль врача одобрена')
  expect(screen.queryByRole('link', { name: 'Я врач' })).not.toBeInTheDocument()
  if (status === 'rejected') expect(screen.getByText('Администратор: Уточните специализацию')).toBeInTheDocument()
})
it('distinguishes failed application state from no application and retries by keyboard', async () => {
  vi.mocked(api.get).mockRejectedValueOnce(new Error('network')).mockResolvedValue({ data: [] })
  mount(<DoctorRoleStatus />)
  expect(screen.getByRole('status')).toHaveTextContent('Проверяем статус')
  await screen.findByRole('alert')
  expect(screen.queryByRole('link', { name: 'Я врач' })).not.toBeInTheDocument()
  const user = userEvent.setup()
  await user.tab(); expect(screen.getByRole('button', { name: 'Повторить проверку заявки' })).toHaveFocus()
  await user.keyboard('{Enter}')
  await screen.findByRole('link', { name: 'Я врач' })
})
it('does not show an application form before its state is loaded or if loading fails', async () => {
  vi.mocked(api.get).mockImplementation(async url => { if (url === '/doctor-role-applications/mine') throw Error('network'); return { data: [] } })
  mount(<DoctorRequestPage />)
  expect(screen.queryByLabelText('Специализация')).not.toBeInTheDocument()
  await screen.findByText('Не удалось загрузить ваши заявки.')
  expect(screen.queryByRole('button', { name: 'Отправить на проверку' })).not.toBeInTheDocument()
  vi.mocked(api.get).mockResolvedValue({ data: [] })
  fireEvent.click(screen.getByRole('button', { name: 'Повторить загрузку заявок' }))
  await screen.findByLabelText('Специализация')
})
it.each(['pending', 'approved'] as const)('blocks repeated form for a %s application', async status => {
  vi.mocked(api.get).mockImplementation(async url => ({ data: url === '/doctor-role-applications/mine' ? [application(status)] : [] }))
  mount(<DoctorRequestPage />)
  await screen.findByText(status === 'pending' ? 'Текущая заявка' : 'Заявка одобрена')
  expect(screen.queryByLabelText('Специализация')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Отправить на проверку' })).not.toBeInTheDocument()
})
it('explains a rejection and allows the existing lifecycle with quorum checks', async () => {
  vi.mocked(api.get).mockImplementation(async url => ({ data: url === '/doctor-role-applications/mine' ? [application('rejected')] : [] }))
  mount(<DoctorRequestPage />)
  await screen.findByText('Администратор: Уточните специализацию')
  expect(screen.getByLabelText('Специализация')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Отправить на проверку' })).toBeDisabled()
})
it('keeps application submission failures on screen without an unhandled rejection', async () => {
  vi.mocked(api.get).mockImplementation(async url => ({ data: url === '/doctor-role-applications/reviewers' ? [{ id: 'admin', fio: 'Администратор', email: 'admin@example.com', role: 'admin', specialty: null }] : [] }))
  vi.spyOn(api, 'post').mockRejectedValue({ response: { data: { detail: 'Не удалось отправить заявку' } } })
  mount(<DoctorRequestPage />)
  fireEvent.change(await screen.findByLabelText('Специализация'), { target: { value: 'Кардиология' } })
  fireEvent.click(await screen.findByRole('checkbox'))
  fireEvent.click(screen.getByRole('button', { name: 'Отправить на проверку' }))
  await screen.findByText('Не удалось отправить заявку')
  expect(api.post).toHaveBeenCalledTimes(1)
})
it('retries history errors rather than presenting an empty history', async () => {
  vi.mocked(api.get).mockImplementation(async url => { if (url === '/patients') throw Error('network'); return { data: [] } })
  mount(<PatientDashboard />)
  await screen.findByText('Не удалось загрузить вашу историю.')
  expect(screen.queryByText('Ваши медицинские записи появятся здесь')).not.toBeInTheDocument()
  vi.mocked(api.get).mockImplementation(async url => ({ data: url === '/patients' ? [patient] : [] }))
  fireEvent.click(screen.getByRole('button', { name: 'Повторить загрузку истории' }))
  await screen.findByText('Ваши медицинские записи появятся здесь')
})
it.each([{ patients: [] }, { patients: [patient] }])('offers a new doctor addition before import, even with an own card ($patients)', async ({ patients }) => {
  useAuthStore.setState({ user: { ...useAuthStore.getState().user!, role: 'doctor' } })
  vi.mocked(api.get).mockImplementation(async url => ({ data: url === '/patients' ? patients : url === '/inbox/tasks' || url === '/cases' ? { items: [], total: 0 } : [] }))
  mount(<DoctorDashboard />)
  await screen.findByRole('link', { name: 'Импорт документов' })
  expect(screen.getByRole('link', { name: 'Импорт документов' })).toHaveAttribute('href', '/upload')
  expect(screen.getAllByRole('link', { name: 'Добавить пациента' })[0]).toHaveAttribute('href', '/patients?create=1')
})
it('retains a populated dashboard and shows existing inbox invitations', async () => {
  useAuthStore.setState({ user: { ...useAuthStore.getState().user!, role: 'doctor' } })
  vi.mocked(api.get).mockImplementation(async url => ({ data: url === '/patients' ? [patient, { ...patient, id: 'other', access_context: 'created', fio: 'Другой Пациент' }] : url === '/inbox/tasks' ? { items: [{ key: 'invite', kind: 'invitation', id: 'invite', case_id: 'case', actor_name: 'Коллега', context: 'Материалов: 1', created_at: '2026-10-12' }], total: 1 } : url === '/cases' ? { items: [], total: 0 } : [] }))
  mount(<DoctorDashboard />)
  await screen.findByText('Другой Пациент')
  expect(screen.getByRole('link', { name: 'Новый клинический случай' })).toHaveAttribute('href', '/cases/new')
  expect(await screen.findByRole('link', { name: 'Рассмотреть приглашение' })).toHaveAttribute('href', '/cases/case')
})
it('opens creation directly, labels fields and confines keyboard focus to the dialog', async () => {
  useAuthStore.setState({ user: { ...useAuthStore.getState().user!, role: 'doctor' } })
  mount(<PatientListPage />, '/patients?create=1')
  await screen.findByRole('dialog', { name: 'Новый пациент' })
  expect(screen.getByLabelText('Фамилия *')).toHaveFocus()
  const user = userEvent.setup()
  screen.getByRole('button', { name: 'Отмена' }).focus()
  await user.tab()
  expect(screen.getByRole('button', { name: 'Закрыть создание пациента' })).toHaveFocus()
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})
it('ignores a create URL for a patient role', async () => {
  mount(<PatientListPage />, '/patients?create=1')
  await act(async () => {})
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Добавить пациента' })).not.toBeInTheDocument()
})
it('does not infer doctor onboarding from failed patient loading and retries it', async () => {
  useAuthStore.setState({ user: { ...useAuthStore.getState().user!, role: 'doctor' } })
  vi.mocked(api.get).mockImplementation(async url => { if (url === '/patients') throw Error('network'); return { data: url === '/inbox/tasks' || url === '/cases' ? { items: [], total: 0 } : [] } })
  mount(<DoctorDashboard />)
  await screen.findByText('network')
  expect(screen.queryByRole('link', { name: 'Добавить пациента' })).not.toBeInTheDocument()
  vi.mocked(api.get).mockImplementation(async url => ({ data: url === '/patients' ? [patient] : url === '/inbox/tasks' || url === '/cases' ? { items: [], total: 0 } : [] }))
  fireEvent.click(screen.getByText('network').closest('p')!.querySelector('button')!)
  await screen.findByRole('link', { name: 'Импорт документов' })
})
it('does not substitute a previously opened shared card for the own patient history', async () => {
  usePatientsStore.setState({ currentPatient: { id: 'shared', fio: 'Другая Карточка', firstName: '', lastName: '', status: 'confirmed', accessContext: 'shared', recordCount: 2 } })
  mount(<PatientDashboard />)
  await screen.findByRole('link', { name: 'Открыть карточку' })
  expect(screen.getByRole('link', { name: 'Открыть карточку' })).toHaveAttribute('href', '/patients/own')
  expect(screen.queryByText('Другая Карточка')).not.toBeInTheDocument()
})
it('gives a truthful fallback when the server returns no rejection note', async () => {
  const rejected = application('rejected')
  rejected.reviews[0].note = null
  vi.mocked(api.get).mockResolvedValue({ data: [rejected] })
  mount(<DoctorRoleStatus />)
  await screen.findByText('Проверяющий не указал причину отказа.')
})
it('preserves a dirty patient form when closing is cancelled and shares one close policy', async () => {
  useAuthStore.setState({ user: { ...useAuthStore.getState().user!, role: 'doctor' } })
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
  mount(<PatientListPage />, '/patients?create=1')
  const field = await screen.findByLabelText('Фамилия *')
  fireEvent.change(field, { target: { value: 'Несохранённый пациент' } })
  const user = userEvent.setup()
  await user.keyboard('{Escape}')
  expect(confirm).toHaveBeenCalledTimes(1)
  expect(field).toHaveValue('Несохранённый пациент')
  expect(screen.getByRole('dialog')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Закрыть создание пациента' }))
  expect(confirm).toHaveBeenCalledTimes(2)
  expect(field).toHaveValue('Несохранённый пациент')
  fireEvent.click(screen.getByRole('dialog').parentElement!)
  expect(confirm).toHaveBeenCalledTimes(3)
  expect(field).toHaveValue('Несохранённый пациент')
  confirm.mockReturnValue(true)
  fireEvent.click(screen.getByRole('button', { name: 'Отмена' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})
