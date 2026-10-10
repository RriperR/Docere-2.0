import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { caseApi, type CaseView, type Page } from '../../api/cases'
import CasesPage from './CasesPage'
import CaseSummaryCard from './CaseSummaryCard'

afterEach(() => vi.restoreAllMocks())

it('does not show an empty state while loading and ignores superseded filters', async () => {
  const reads: Array<(page: Page<CaseView>) => void> = []
  vi.spyOn(caseApi, 'list').mockImplementation(() => new Promise(resolve => reads.push(resolve)))
  render(<MemoryRouter><CasesPage /></MemoryRouter>)
  expect(screen.getByRole('status')).toHaveTextContent('Загружаем')
  expect(screen.queryByText('Начните первый совместный разбор')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Участвую' }))
  await act(async () => reads[1]({ items: [], total: 0 }))
  expect(screen.getByText('В этой категории пока нет случаев')).toBeInTheDocument()
  await act(async () => reads[0]({ items: [], total: 99 }))
  expect(screen.queryByLabelText('Страницы клинических случаев')).not.toBeInTheDocument()
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})

it('offers a retry after failure without claiming that there are no cases', async () => {
  vi.spyOn(caseApi, 'list').mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ items: [], total: 0 })
  render(<MemoryRouter><CasesPage /></MemoryRouter>)
  expect(await screen.findByRole('alert')).toBeVisible()
  expect(screen.queryByText('Начните первый совместный разбор')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
  expect(await screen.findByText('Начните первый совместный разбор')).toBeVisible()
})

it('does not render clinical text in a neutral invitation card', () => {
  const item: CaseView = { id: 'case', status: 'active', membership_status: 'pending', coordinator_id: 'doctor',
    coordinator_name: 'Координатор', management_members: [], unread_messages: 0, patient_name: null,
    material_count: 2, accessible: false, case: null, invitation_terms: '' }
  render(<MemoryRouter><CaseSummaryCard item={item} /></MemoryRouter>)
  expect(screen.getByRole('heading')).toHaveTextContent('Приглашение в разбор')
  expect(screen.getByText(/после принятия приглашения/)).toBeVisible()
  expect(screen.queryByText('Вопрос для коллег')).not.toBeInTheDocument()
})
