import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { AiDocument } from '../../api/importAi'
import AiSuggestions from './AiSuggestions'

const document: AiDocument = {
  file_id: 'file', filename: 'scan.png', path: 'scan.png', status: 'completed', page_count: 1, checksum: 'hash', error_code: null,
  result: { fields: {
    fio: { value: 'Тестовый пациент', sources: [{ page: 1, excerpt: 'Пациент' }] },
    clinical_summary: { value: 'Сведения из документа', sources: [{ page: 1, excerpt: 'Обследование' }] },
  } },
}
afterEach(cleanup)

it('applies only allowed fields and opens their actual source page by keyboard', async () => {
  const apply = vi.fn(), source = vi.fn(), user = userEvent.setup()
  render(<AiSuggestions document={document} runId="run" canApplyIdentity={false} onApply={apply} onSource={source} />)
  expect(apply).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Заполнить пустые поля' }))
  expect(apply).toHaveBeenCalledTimes(1)
  expect(apply).toHaveBeenCalledWith('clinical_summary', 'Сведения из документа', { run_id: 'run', file_id: 'file', fields: ['clinical_summary'] }, true)
  const proposal = screen.getByRole('article', { name: 'Предложение: Клиническое описание' })
  const disclosure = within(proposal).getByText('Источники предложения (1)')
  await user.click(disclosure)
  screen.getByRole('button', { name: 'Стр. 1: «Обследование»' }).focus()
  await user.keyboard('{Enter}')
  expect(source).toHaveBeenCalledWith('file', 1)
})

it('shows current values separately and never includes nonempty fields in bulk fill', () => {
  const apply = vi.fn()
  render(<AiSuggestions document={document} runId="run" canApplyIdentity currentValues={{ fio: '', clinical_summary: 'Правка врача' }} onApply={apply} onSource={vi.fn()} />)
  const proposal = screen.getByRole('article', { name: 'Предложение: Клиническое описание' })
  expect(within(proposal).getByText('Правка врача')).toBeVisible()
  expect(within(proposal).getByText('Сведения из документа')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Заполнить пустые поля' }))
  expect(apply).toHaveBeenCalledTimes(1)
  expect(apply).toHaveBeenCalledWith('fio', 'Тестовый пациент', { run_id: 'run', file_id: 'file', fields: ['fio'] }, true)
  fireEvent.click(screen.getByRole('button', { name: 'Заменить: Клиническое описание' }))
  expect(apply).toHaveBeenLastCalledWith('clinical_summary', 'Сведения из документа', { run_id: 'run', file_id: 'file', fields: ['clinical_summary'] })
})

it('keeps identity conflicts and analysis errors visible without opening details', () => {
  render(<AiSuggestions document={{ ...document, status: 'failed', error_code: 'invalid_response', result: { patient_conflict: true, issues: ['conflicting:event_date'] } }}
    runId="run" canApplyIdentity onApply={vi.fn()} onSource={vi.fn()} />)
  expect(screen.getByText('Ответ AI не прошёл проверку. Предложения не применены.')).toBeVisible()
  expect(screen.getByText(/Сведения о пациенте противоречат/)).toBeVisible()
  expect(screen.getByText('Дата события: противоречащие сведения')).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Заполнить пустые поля' })).not.toBeInTheDocument()
})

it('does not allow applying a document containing multiple patients', () => {
  const apply = vi.fn()
  render(<AiSuggestions document={{ ...document, result: { ...document.result, multiple_patients: true } }} runId="run" canApplyIdentity onApply={apply} onSource={vi.fn()} />)
  expect(screen.getByRole('alert')).toHaveTextContent('В документе разные пациенты')
  expect(screen.getByRole('button', { name: 'Применить: ФИО' })).toBeDisabled()
  expect(apply).not.toHaveBeenCalled()
})
