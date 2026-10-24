import { useEffect, useState } from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import api from '../../api/api'
import type { ClinicalCase } from '../../api/cases'
import CaseDiscussion from './CaseDiscussion'

const state = vi.hoisted(() => ({ draft: { text: '', parent_id: null as string | null, opinion_id: null as string | null } }))
vi.mock('../../hooks/useCaseWorkDraft', () => ({
  emptyWorkDraft: {},
  useCaseWorkDraft: (_id: string, kind: string, _enabled: boolean, _content: unknown, restore: (value: unknown) => void) => {
    const [ready, setReady] = useState(false)
    useEffect(() => {
      restore({ text: kind === 'message' ? state.draft.text : '', record_ids: [], attachment_id: null,
        parent_id: state.draft.parent_id, opinion_id: state.draft.opinion_id, idempotency_key: 'key' })
      setReady(true)
      // Имитация однократного восстановления серверного черновика до ready.
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [kind])
    return { ready, conflict: false, flush: async () => true, refresh: async () => undefined, status: 'saved' }
  },
}))
vi.mock('./CaseMaterialPicker', () => ({ default: () => null }))
vi.mock('./DraftStatus', () => ({ default: () => null }))
afterEach(() => { cleanup(); vi.restoreAllMocks(); state.draft = { text: '', parent_id: null, opinion_id: null } })

const c = { id: 'case', coordinator_id: 'owner', status: 'active', sequence: 1, members: [{ user_id: 'doctor', name: 'Коллега', status: 'accepted' }] } as ClinicalCase
function setup() {
  vi.spyOn(api, 'get').mockImplementation(async url => String(url).endsWith('/opinions/target')
    ? { data: { id: 'target', question: 'Сверьте дату в источнике', requester_id: 'owner', assignee_id: 'doctor', status: 'open', record_id: 'record' } }
    : { data: { items: [], total: 0 } })
  const post = vi.spyOn(api, 'post').mockResolvedValue({ data: {} })
  const onOpen = vi.fn()
  render(<MemoryRouter initialEntries={['/cases/case?opinion=target']}><CaseDiscussion c={c} userId="doctor" onChange={vi.fn(async () => undefined)} onOpen={onOpen} /></MemoryRouter>)
  return { post, onOpen }
}
it('opens an addressed request with its source and an explicitly linked reply form', async () => {
  const { post, onOpen } = setup()
  await screen.findByRole('region', { name: 'Запрос из входящих' })
  const field = await screen.findByRole('textbox', { name: 'Ответ на запрос мнения' })
  expect(field).toHaveFocus()
  await userEvent.click(screen.getByRole('button', { name: 'Открыть материал запроса' }))
  expect(onOpen).toHaveBeenCalledWith('record', null)
  await userEvent.type(field, 'Дата проверена по источнику')
  await userEvent.click(screen.getByRole('button', { name: 'Отправить ответ на запрос' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith('/cases/case/messages', expect.objectContaining({ body: 'Дата проверена по источнику', opinion_id: 'target', record_id: 'record' })))
})
it('keeps the existing text and reply destination until the doctor explicitly switches context', async () => {
  state.draft = { text: 'Личный черновик', parent_id: 'previous', opinion_id: null }
  setup()
  const field = await screen.findByRole('textbox', { name: 'Ответ на сообщение' })
  expect(field).toHaveValue('Личный черновик')
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
  await userEvent.click(screen.getByRole('button', { name: 'Ответить на этот запрос' }))
  expect(screen.getByRole('textbox', { name: 'Ответ на сообщение' })).toHaveValue('Личный черновик')
  confirm.mockReturnValue(true)
  await userEvent.click(screen.getByRole('button', { name: 'Ответить на этот запрос' }))
  expect(screen.getByRole('textbox', { name: 'Ответ на запрос мнения' })).toHaveValue('Личный черновик')
})
