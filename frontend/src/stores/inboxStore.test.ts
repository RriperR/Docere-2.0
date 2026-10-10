import { beforeEach, expect, it, vi } from 'vitest'
import api from '../api/api'
import { useInboxStore } from './inboxStore'
beforeEach(() => { vi.restoreAllMocks(); useInboxStore.getState().reset() })
it('preserves last counts on network failure and rejects results from the previous session', async () => {
  vi.spyOn(api, 'get').mockResolvedValueOnce({ data: { tasks: 3, unread_events: 2 } }).mockRejectedValueOnce(new Error('offline'))
  await useInboxStore.getState().refresh()
  await useInboxStore.getState().refresh()
  expect(useInboxStore.getState().counts).toEqual({ tasks: 3, unread_events: 2 })
  expect(useInboxStore.getState().error).toBe(true)
  let resolve!: (value: unknown) => void
  vi.mocked(api.get).mockImplementationOnce(() => new Promise(done => { resolve = done }))
  const loading = useInboxStore.getState().refresh()
  useInboxStore.getState().reset()
  resolve({ data: { tasks: 99, unread_events: 99 } })
  await loading
  expect(useInboxStore.getState().counts).toBeNull()
})
