import MockAdapter from 'axios-mock-adapter'
import { afterEach, expect, it } from 'vitest'
import api from '../api/api'
import { useAuthStore } from './authStore'

const mock = new MockAdapter(api)
afterEach(() => { mock.reset(); useAuthStore.getState().logout() })

it('explains an authentication rate limit without claiming invalid credentials', async () => {
  mock.onPost('/auth/login').reply(429, { detail: 'Too many authentication attempts' })
  await expect(useAuthStore.getState().login('doctor@example.test', 'example')).rejects.toThrow()
  expect(useAuthStore.getState().error).toBe('Слишком много попыток. Подождите минуту и попробуйте снова.')
  expect(useAuthStore.getState().isLoading).toBe(false)
})
