import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { usePatientsStore } from '../../stores/patientsStore'
import { useAuthStore } from '../../stores/authStore'
import { useShareRequestsStore } from '../../stores/shareRequestsStore'
import PatientDetailsPage from './PatientDetailsPage'

const patients = usePatientsStore.getState(), auth = useAuthStore.getState(), shares = useShareRequestsStore.getState()
afterEach(() => { cleanup(); usePatientsStore.setState(patients, true); useAuthStore.setState(auth, true); useShareRequestsStore.setState(shares, true); vi.restoreAllMocks() })
it('keeps identity and timeline primary while retaining access management and technical details', async () => {
  useAuthStore.setState({ user: { ...auth.user!, id: 'doctor', role: 'doctor' } })
  usePatientsStore.setState({ isLoading: false, error: null, currentPatient: { id: 'patient', fio: 'Тестовая Анна', firstName: 'Анна', lastName: 'Тестовая', birthday: '1987-03-12', email: '', phone: '', status: 'draft', accessContext: 'shared', recordCount: 1 }, patientRecords: [{ id: 'record', title: 'Исследование', status: 'unconfirmed', recordType: 'exam_result', eventDate: '2026-10-24', creatorUserId: 'other', creatorFio: 'Коллега', commentsCount: 0, attachmentsCount: 0, createdAt: '2026-10-24T10:00:00Z', updatedAt: '2026-10-24T10:00:00Z' }], fetchPatientById: vi.fn(), fetchPatientRecords: vi.fn(), clearActiveRecord: vi.fn() })
  useShareRequestsStore.setState({ outbox: [], fetchOutbox: vi.fn() })
  render(<MemoryRouter initialEntries={['/patients/patient']}><Routes><Route path="/patients/:id" element={<PatientDetailsPage />} /></Routes></MemoryRouter>)
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Тестовая Анна' })).toBeVisible())
  expect(screen.getByRole('link', { name: 'Добавить документы' })).toHaveAttribute('href', '/upload?patient=patient')
  expect(screen.getByRole('link', { name: 'Создать разбор' })).toHaveAttribute('href', '/cases/new?patient=patient')
  expect(screen.getByText('Не подтверждена')).toBeVisible()
  expect(screen.getAllByText('Получена от коллеги')[0]).toBeVisible()
  expect(screen.queryByText('unconfirmed')).not.toBeInTheDocument()
  expect(screen.getByText('Идентификатор карточки: patient')).not.toBeVisible()
  fireEvent.click(screen.getByText('Сведения о пациенте и карточке'))
  expect(screen.getByText('Идентификатор карточки: patient')).toBeVisible()
  expect(screen.getByRole('heading', { name: 'Выданные доступы', hidden: true })).not.toBeVisible()
  fireEvent.click(screen.getByText('Управление доступом к записям'))
  expect(screen.getByRole('heading', { name: 'Выданные доступы', hidden: true })).toBeVisible()
})
