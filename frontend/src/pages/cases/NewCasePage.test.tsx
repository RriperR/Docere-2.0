import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import api from '../../api/api'
import { caseApi } from '../../api/cases'
import NewCasePage from './NewCasePage'

afterEach(() => { cleanup(); vi.restoreAllMocks() })
it('keeps selection across wizard steps and clears it when a different patient is selected', async () => {
  vi.spyOn(caseApi, 'patients').mockResolvedValue([{ id: 'one', fio: 'Пациент Один', date_of_birth: '1990-01-01' }, { id: 'two', fio: 'Пациент Два', date_of_birth: null }])
  vi.spyOn(api, 'get').mockImplementation(async url => ({ data: { id: String(url).split('/').slice(-1)[0], fio: 'Выбранный пациент', date_of_birth: '1990-01-01' } }))
  vi.spyOn(caseApi, 'available').mockImplementation(async id => ({ items: [{ id: `record-${id}`, title: 'Исследование', clinical_summary: '', record_type: 'other', event_date: '2026-01-01', status: 'unconfirmed' }], total: 1 }))
  render(<MemoryRouter><NewCasePage /></MemoryRouter>)
  fireEvent.change(screen.getByLabelText('Найти пациента'), { target: { value: 'Пациент' } })
  fireEvent.click(screen.getByRole('button', { name: /^Найти$/ }))
  fireEvent.click(await screen.findByRole('button', { name: /Пациент Один/ }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Перейти к материалам' })).toBeEnabled())
  fireEvent.click(screen.getByText('Перейти к материалам'))
  fireEvent.click(await screen.findByRole('checkbox', { name: /Исследование/ }))
  fireEvent.click(screen.getByText('Сформулировать вопрос'))
  fireEvent.change(screen.getByLabelText('Вопрос для обсуждения'), { target: { value: 'Вопрос коллеге' } })
  fireEvent.click(screen.getByText('Назад к материалам'))
  expect(screen.getByRole('checkbox', { name: /Исследование/ })).toBeChecked()
  fireEvent.click(screen.getByText('Назад к пациенту'))
  fireEvent.click(screen.getByRole('button', { name: /^Найти$/ }))
  fireEvent.click(await screen.findByRole('button', { name: /Пациент Два/ }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Перейти к материалам' })).toBeEnabled())
  fireEvent.click(screen.getByText('Перейти к материалам'))
  expect(await screen.findByRole('checkbox', { name: /Исследование/ })).not.toBeChecked()
  fireEvent.click(screen.getByText('Сформулировать вопрос'))
  expect(screen.getByLabelText('Вопрос для обсуждения')).toHaveValue('Вопрос коллеге')
})

it('preselects only explicitly linked records after checking access and their patient', async () => {
  vi.spyOn(api, 'get').mockImplementation(async url => {
    if (String(url).startsWith('/patients/')) return { data: { id: 'one', fio: 'Пациент Один' } }
    if (url === '/records/denied') throw new Error('403')
    return { data: { id: String(url).split('/').slice(-1)[0], patient_passport_id: url === '/records/other' ? 'two' : 'one' } }
  })
  vi.spyOn(caseApi, 'available').mockResolvedValue({ items: [{ id: 'allowed', title: 'Разрешённая запись', clinical_summary: '', record_type: 'other', event_date: '2026-10-13', status: 'unconfirmed' }], total: 1 })
  render(<MemoryRouter initialEntries={['/cases/new?patient=one&record=allowed&record=other&record=denied']}><NewCasePage /></MemoryRouter>)
  await screen.findByText(/Часть записей из ссылки недоступна/)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Перейти к материалам' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Перейти к материалам' }))
  expect(screen.getByText('Выбрано: 1 из 1 доступных · максимум 100')).toBeVisible()
  expect(screen.getByRole('checkbox', { name: /Разрешённая запись/ })).toBeChecked()
  fireEvent.click(screen.getByRole('checkbox', { name: /Разрешённая запись/ }))
  expect(screen.getByText('Выбрано: 0 из 1 доступных · максимум 100')).toBeVisible()
})

it('rejects a foreign patient ID without enabling the next step', async () => {
  vi.spyOn(api, 'get').mockRejectedValue(Error('403'))
  vi.spyOn(caseApi, 'available').mockRejectedValue(Error('403'))
  render(<MemoryRouter initialEntries={['/cases/new?patient=foreign&record=secret']}><NewCasePage /></MemoryRouter>)
  await screen.findByText(/Не удалось проверить карточку/)
  expect(screen.getByRole('button', { name: 'Перейти к материалам' })).toBeDisabled()
})
