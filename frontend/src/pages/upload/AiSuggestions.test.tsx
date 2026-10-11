import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import AiSuggestions from './AiSuggestions'

const document = { file_id: 'file', filename: 'scan.png', path: 'scan.png', status: 'completed', page_count: 1, checksum: 'hash', error_code: null,
  result: { fields: { fio: { value: 'Тестовый пациент', sources: [{ page: 1, excerpt: 'Пациент' }] }, clinical_summary: { value: 'Сведения из документа', sources: [{ page: 1, excerpt: 'Обследование' }] } } } }
afterEach(cleanup)
it('applies only allowed fields and opens their actual source page', () => {
  const apply = vi.fn(), source = vi.fn()
  render(<AiSuggestions document={document} runId="run" canApplyIdentity={false} onApply={apply} onSource={source} />)
  fireEvent.click(screen.getByRole('button', { name: 'Заполнить пустые поля' }))
  expect(apply).toHaveBeenCalledTimes(1)
  expect(apply).toHaveBeenCalledWith('clinical_summary', 'Сведения из документа', { run_id: 'run', file_id: 'file', fields: ['clinical_summary'] }, true)
  fireEvent.click(screen.getByRole('button', { name: 'Стр. 1: «Обследование»' }))
  expect(source).toHaveBeenCalledWith('file', 1)
})
