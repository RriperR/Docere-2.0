import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import api from '../../api/api'
import type { ClinicalCase } from '../../api/cases'
import CaseConclusion from './CaseConclusion'

vi.mock('../../hooks/useCaseWorkDraft', () => ({
  emptyWorkDraft: {}, useCaseWorkDraft: () => ({ ready: true, conflict: false, flush: async () => true, refresh: async () => undefined, status: 'saved' }),
}))
vi.mock('./CaseMaterialPicker', () => ({ default: () => null }))
vi.mock('./DraftStatus', () => ({ default: () => null }))
afterEach(() => { cleanup(); vi.restoreAllMocks() })

it('requires an explicit choice when closing with a different private draft', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({ data: {} })
  vi.spyOn(api, 'get').mockImplementation(async url => String(url).endsWith('closure-preview') ? { data: { open_requests: 0, version: 8 } } : { data: { total: 2, items: [{ id: 'v2', number: 2, summary: 'Сохранённый итог', findings: '', next_actions: '', source_ids: ['r1'], sources: [{ id: 'r1', title: 'Анализ', event_date: '2026-09-01' }], created_at: '2026-09-01' }] } })
  const c = { id: 'c1', version: 8, status: 'active' } as ClinicalCase
  render(<MemoryRouter><CaseConclusion c={c} owner onChange={vi.fn(async () => undefined)} /></MemoryRouter>)
  await screen.findByText('Сохранённый итог')
  expect(screen.getByRole('button', { name: 'Анализ · 01.09.2026' })).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: 'Составить новую версию итога' }))
  await userEvent.clear(screen.getByLabelText('Краткое резюме'))
  await userEvent.type(screen.getByLabelText('Краткое резюме'), 'Личный новый итог')
  await userEvent.click(screen.getByRole('button', { name: 'Завершить разбор' }))
  await screen.findByRole('dialog', { name: 'Завершение разбора' })
  expect(screen.getByRole('button', { name: 'Подтвердить завершение' })).toBeDisabled()
  expect(post).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('checkbox', { name: /Завершить с сохранённой версией/ }))
  await userEvent.click(screen.getByRole('button', { name: 'Подтвердить завершение' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith('/cases/c1/close', { version: 8, cancel_open_requests: false }))
})

it('keeps the latest saved version visible while older versions load on demand', async () => {
  const version = (number: number) => ({ id: `v${number}`, number, summary: `Итог ${number}`, findings: '', next_actions: '', source_ids: [], sources: [], created_at: '2026-10-01' })
  const get = vi.spyOn(api, 'get').mockImplementation(async (_url, config) => {
    const params = config?.params as { offset?: number } | undefined
    const offset = params?.offset ?? 0
    return { data: { total: 12, items: offset === 0 ? [version(12)] : offset === 1 ? [version(11), version(10)] : [version(1)] } }
  })
  render(<MemoryRouter><CaseConclusion c={{ id: 'case', status: 'active', version: 1 } as ClinicalCase} owner onChange={vi.fn(async () => undefined)} /></MemoryRouter>)
  await screen.findByText('Итог 12')
  expect(get).toHaveBeenCalledTimes(1)
  expect(screen.queryByText('Итог 11')).not.toBeInTheDocument()
  await userEvent.click(screen.getByText('Предыдущие версии (11)'))
  await screen.findByText('Итог 11')
  expect(screen.getByText('Итог 12')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: 'Ранее' }))
  await screen.findByText('Итог 1')
  expect(screen.getByText('Итог 12')).toBeVisible()
  expect(get).toHaveBeenLastCalledWith('/cases/case/conclusions', expect.objectContaining({ params: { offset: 11, limit: 10 } }))
})
