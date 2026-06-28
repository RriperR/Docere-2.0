import axios from 'axios'
import MockAdapter from 'axios-mock-adapter'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import api from './api'
import { useAuthStore } from '../stores/authStore'

const initialTokens = {
  access_token: 'expired-access-token',
  refresh_token: 'valid-refresh-token',
  token_type: 'bearer',
}

describe('API token refresh', () => {
  const apiMock = new MockAdapter(api)
  const axiosMock = new MockAdapter(axios)

  beforeEach(() => {
    apiMock.reset()
    axiosMock.reset()
    useAuthStore.getState().setTokens(initialTokens)
  })

  afterEach(() => {
    useAuthStore.getState().logout()
  })

  it('refreshes an expired access token and retries the request', async () => {
    apiMock.onGet('/protected').replyOnce(401).onGet('/protected').reply(200, { ok: true })
    axiosMock.onPost('/auth/refresh').reply(200, {
      access_token: 'new-access-token',
      refresh_token: 'new-refresh-token',
      token_type: 'bearer',
    })

    const response = await api.get('/protected')

    expect(response.data).toEqual({ ok: true })
    expect(useAuthStore.getState().tokens?.access_token).toBe('new-access-token')
    expect(apiMock.history.get[1].headers?.Authorization).toBe('Bearer new-access-token')
  })

  it('uses one refresh request for concurrent unauthorized responses', async () => {
    apiMock.onGet('/first').replyOnce(401).onGet('/first').reply(200)
    apiMock.onGet('/second').replyOnce(401).onGet('/second').reply(200)
    axiosMock.onPost('/auth/refresh').reply(200, {
      access_token: 'new-access-token',
      refresh_token: 'new-refresh-token',
      token_type: 'bearer',
    })

    await Promise.all([api.get('/first'), api.get('/second')])

    expect(axiosMock.history.post).toHaveLength(1)
  })

  it('logs out only after refresh fails', async () => {
    apiMock.onGet('/protected').reply(401)
    axiosMock.onPost('/auth/refresh').reply(401)

    await expect(api.get('/protected')).rejects.toBeDefined()

    expect(useAuthStore.getState().isAuthenticated).toBe(false)
    expect(useAuthStore.getState().tokens).toBeNull()
  })

  it('does not refresh a rejected login request', async () => {
    apiMock.onPost('/auth/login').reply(401)

    await expect(api.post('/auth/login', { email: 'wrong@example.com', password: 'wrong' })).rejects.toBeDefined()

    expect(axiosMock.history.post).toHaveLength(0)
  })
})
