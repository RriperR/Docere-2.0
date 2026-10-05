import { afterEach, expect, it, vi } from 'vitest'
import api from '../api/api'
import { useNotificationsStore } from './notificationsStore'

function pendingCount() {
  let resolve!: (result: { data: { unread: number; version: string } }) => void
  const promise = new Promise<{ data: { unread: number; version: string } }>(done => { resolve = done })
  return { promise, resolve }
}

afterEach(() => { useNotificationsStore.getState().reset(); vi.restoreAllMocks() })

it('does not restore the previous user notifications after logout', async () => {
  const request = pendingCount()
  vi.spyOn(api, 'get').mockReturnValue(request.promise)
  const refresh = useNotificationsStore.getState().refresh()
  useNotificationsStore.getState().reset()
  request.resolve({ data: { unread: 7, version: 'old-user' } })
  await refresh
  expect(useNotificationsStore.getState()).toMatchObject({ unread: 0, version: '', revision: 0 })
})

it('ignores a superseded refresh that arrives after a newer response', async () => {
  const first = pendingCount(), second = pendingCount()
  vi.spyOn(api, 'get').mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
  const refresh = useNotificationsStore.getState().refresh
  const old = refresh(), current = refresh()
  second.resolve({ data: { unread: 2, version: 'new' } })
  await current
  first.resolve({ data: { unread: 10, version: 'old' } })
  await old
  expect(useNotificationsStore.getState()).toMatchObject({ unread: 2, version: 'new', revision: 1 })
})
