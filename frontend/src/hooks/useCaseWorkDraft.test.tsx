import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { useState } from 'react'
import { AxiosError } from 'axios'
import api from '../api/api'
import { emptyWorkDraft, useCaseWorkDraft, type WorkDraftContent } from './useCaseWorkDraft'

function Form() {
  const [content, setContent] = useState<WorkDraftContent>(emptyWorkDraft)
  const draft = useCaseWorkDraft('case', 'message', true, content, setContent)
  return <><textarea aria-label="Текст" disabled={!draft.ready} value={content.text} onChange={event => setContent({ ...content, text: event.target.value })} />
    <p>{draft.error}</p><p>{draft.status}</p><button disabled={!draft.ready} onClick={() => void draft.flush()}>Сохранить</button>
    <button onClick={() => void draft.reload()}>Восстановить</button></>
}
afterEach(() => { cleanup(); vi.restoreAllMocks() })
it('restores the private form and saves edits made while an earlier save is in flight', async () => {
  vi.spyOn(api, 'get').mockResolvedValue({ data: { version: 3, content: { ...emptyWorkDraft, text: 'Сохранённый текст' }, updated_at: '2026-10-10' } })
  let complete!: (value: unknown) => void
  const first = new Promise(resolve => { complete = resolve })
  const put = vi.spyOn(api, 'put').mockImplementationOnce(() => first as ReturnType<typeof api.put>).mockResolvedValueOnce({ data: { version: 5 } })
  render(<Form />)
  await screen.findByDisplayValue('Сохранённый текст')
  fireEvent.change(screen.getByLabelText('Текст'), { target: { value: 'Первая правка' } })
  expect(screen.getByText('Последние изменения ещё не сохранены')).toBeVisible()
  fireEvent.click(screen.getByText('Сохранить'))
  fireEvent.change(screen.getByLabelText('Текст'), { target: { value: 'Следующая правка' } })
  fireEvent.click(screen.getByText('Сохранить'))
  await act(async () => { complete({ data: { version: 4 } }); await first })
  await waitFor(() => expect(put).toHaveBeenCalledTimes(2))
  expect(put.mock.calls[1][1]).toMatchObject({ version: 4, content: { text: 'Следующая правка' } })
})
it('retains local text on conflict and requires explicit confirmation before restoring another tab', async () => {
  vi.spyOn(api, 'get').mockResolvedValueOnce({ data: { version: 1, content: emptyWorkDraft } })
    .mockResolvedValueOnce({ data: { version: 2, content: { ...emptyWorkDraft, text: 'Текст другой вкладки' } } })
  const cause = new AxiosError('conflict')
  cause.response = { status: 409 } as AxiosError['response']
  const put = vi.spyOn(api, 'put').mockRejectedValue(cause)
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
  render(<Form />)
  await waitFor(() => expect(screen.getByLabelText('Текст')).toBeEnabled())
  fireEvent.change(screen.getByLabelText('Текст'), { target: { value: 'Мой текст' } })
  fireEvent.click(screen.getByText('Сохранить'))
  await screen.findByText(/Ваш текст остаётся в форме/)
  expect(screen.getByLabelText('Текст')).toHaveValue('Мой текст')
  fireEvent.click(screen.getByText('Сохранить'))
  expect(put).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByText('Восстановить'))
  expect(confirm).toHaveBeenCalledTimes(1)
  expect(screen.getByLabelText('Текст')).toHaveValue('Мой текст')
  confirm.mockReturnValue(true)
  fireEvent.click(screen.getByText('Восстановить'))
  await screen.findByDisplayValue('Текст другой вкладки')
})
