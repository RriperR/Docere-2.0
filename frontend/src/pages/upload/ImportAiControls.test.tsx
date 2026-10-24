import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { AiDocument, AiRun } from '../../api/importAi'
import type { useImportAi } from './useImportAi'
import ImportAiControls from './ImportAiControls'

afterEach(cleanup)

function aiState(statuses: string[]) {
  return {
    capabilities: null, run: { id: 'run', status: 'running', documents: statuses.map((status, index) => ({
      file_id: `file-${index}`, status, result: {},
    } as AiDocument)) } as AiRun,
    active: true, error: 'Не удалось получить состояние AI. Повторите запрос.', busy: false,
    history: [], hasOlder: false, cancel: vi.fn(), start: vi.fn(), selectRun: vi.fn(), loadOlder: vi.fn(),
  } as ReturnType<typeof useImportAi>
}

it('keeps active analysis, cancellation and errors visible when settings are collapsed', () => {
  const ai = aiState(['running'])
  render(<ImportAiControls ai={ai} patientCandidates={[]} selection={[]} onSelectionChange={vi.fn()} saving={false} />)
  expect(screen.getByText('Заполнить поля по документам с AI').closest('details')).not.toHaveAttribute('open')
  expect(screen.getByText('Анализ выполняется…')).toBeVisible()
  expect(screen.getByRole('alert')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Отменить анализ' }))
  expect(ai.cancel).toHaveBeenCalledOnce()
})

it('counts completed documents separately from queued, running, errors and cancellations', () => {
  render(<ImportAiControls ai={aiState(['completed', 'queued', 'running', 'failed', 'cancelled'])}
    patientCandidates={[]} selection={[]} onSelectionChange={vi.fn()} saving={false} />)
  expect(screen.getByText(/Завершено документов:/)).toHaveTextContent('Завершено документов: 1 из 5. В очереди и выполняются: 2. Ошибки: 1. Отменено: 1.')
})
