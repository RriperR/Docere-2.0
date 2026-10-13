import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import api from '../../api/api'
import { PatientImportContext } from './PatientImportContext'
import { usePatientImportContext } from './usePatientImportContext'
function Context() { const context = usePatientImportContext(); return <PatientImportContext context={context} /> }
afterEach(() => { cleanup(); vi.restoreAllMocks() })
it('validates the ID with the server before displaying a patient and permits retry without substitution', async () => {
  const get = vi.spyOn(api, 'get').mockRejectedValueOnce({ response: { status: 403 } }).mockResolvedValueOnce({ data: { id: 'foreign', fio: 'Проверенный пациент', date_of_birth: null } })
  render(<MemoryRouter initialEntries={['/upload?patient=foreign']}><Context /></MemoryRouter>)
  await screen.findByRole('alert')
  expect(screen.queryByText(/Импорт для пациента/)).not.toBeInTheDocument()
  expect(get.mock.calls[0][0]).toBe('/patients/foreign')
  fireEvent.click(screen.getByRole('button', { name: 'Повторить проверку карточки' }))
  await screen.findByText('Импорт для пациента: Проверенный пациент')
  fireEvent.click(screen.getByRole('button', { name: 'Продолжить без карточки' }))
  expect(screen.queryByText(/Импорт для пациента/)).not.toBeInTheDocument()
})
