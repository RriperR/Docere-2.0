import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '../../stores/authStore'
import { usePatientsStore } from '../../stores/patientsStore'
import { useShareRequestsStore } from '../../stores/shareRequestsStore'
import { useDoctorRoleApplicationsStore } from '../../stores/doctorRoleApplicationsStore'
import { useInboxStore } from '../../stores/inboxStore'
import { useNotificationsStore } from '../../stores/notificationsStore'
import { DashboardLayout } from './DashboardLayout'

vi.mock('../../api/caseUpdates', () => ({ watchChanges: vi.fn().mockResolvedValue(undefined) }))

beforeEach(() => {
  useAuthStore.setState({
    user: { id: 'doctor', fio: 'Тестовый Врач', first_name: 'Врач', last_name: 'Тестовый', middle_name: null, birthday: null, date_of_birth: null, email: 'doctor@example.com', phone: '', role: 'doctor', status: 'active', specialty: null, photo: null, username: '' },
    refreshUser: vi.fn().mockResolvedValue(undefined), logout: vi.fn(),
  })
  usePatientsStore.setState({ patients: [], fetchPatients: vi.fn().mockResolvedValue(undefined) })
  useShareRequestsStore.setState({ inbox: [], fetchInbox: vi.fn().mockResolvedValue(undefined) })
  useDoctorRoleApplicationsStore.setState({ inbox: [], fetchInbox: vi.fn().mockResolvedValue(undefined) })
  useInboxStore.setState({ counts: null, error: false, refresh: vi.fn().mockResolvedValue(undefined), reset: vi.fn() })
  useNotificationsStore.setState({ unread: 0, refresh: vi.fn().mockResolvedValue(undefined), reset: vi.fn() })
})

it('keeps account controls out of navigation and makes the single account panel keyboard accessible', async () => {
  const user = userEvent.setup()
  render(<MemoryRouter><DashboardLayout /></MemoryRouter>)
  const navigation = screen.getByRole('navigation', { name: 'Основная навигация' })
  expect(within(screen.getByRole('complementary')).queryByText('Врач Тестовый')).not.toBeInTheDocument()
  expect(within(navigation).queryByRole('link', { name: /Настройки/ })).not.toBeInTheDocument()
  expect(within(navigation).queryByRole('button', { name: 'Выйти' })).not.toBeInTheDocument()
  const trigger = screen.getByRole('button', { name: 'Меню аккаунта' })
  trigger.focus()
  await user.keyboard('{Enter}')
  expect(trigger).toHaveAttribute('aria-expanded', 'true')
  await user.tab()
  expect(screen.getByRole('link', { name: 'Профиль и настройки' })).toHaveFocus()
  expect(screen.getByRole('combobox', { name: 'Тема' })).toBeInTheDocument()
  await user.keyboard('{Escape}')
  expect(trigger).toHaveFocus()
  expect(trigger).toHaveAttribute('aria-expanded', 'false')
  await waitFor(() => expect(screen.queryByRole('link', { name: 'Профиль и настройки' })).not.toBeInTheDocument())
})

it('contains keyboard focus in mobile navigation and returns it on Escape', async () => {
  const user = userEvent.setup()
  render(<MemoryRouter><DashboardLayout /></MemoryRouter>)
  const trigger = screen.getByRole('button', { name: 'Открыть меню' })
  await user.click(trigger)
  const panel = screen.getByRole('dialog', { name: 'Навигация по Docere' })
  expect(within(panel).getByRole('button', { name: 'Закрыть меню' })).toHaveFocus()
  await user.tab({ shift: true })
  expect(within(panel).getByRole('link', { name: 'Доступ к записям' })).toHaveFocus()
  await user.tab()
  expect(within(panel).getByRole('button', { name: 'Закрыть меню' })).toHaveFocus()
  await user.keyboard('{Escape}')
  expect(trigger).toHaveFocus()
  expect(trigger).toHaveAttribute('aria-expanded', 'false')
})
