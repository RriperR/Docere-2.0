import { expect, it } from 'vitest'
import { requestId } from './requestId'

it('produces unique version 4 UUIDs using the HTTP-compatible Web Crypto API', () => {
  const ids = Array.from({ length: 100 }, requestId)
  expect(new Set(ids).size).toBe(100)
  for (const id of ids) expect(id).toMatch(/^[\da-f]{8}-[\da-f]{4}-4[\da-f]{3}-[89ab][\da-f]{3}-[\da-f]{12}$/)
})
