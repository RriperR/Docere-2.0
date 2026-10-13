#!/usr/bin/env node
/** Проверить готовность уже созданного синтетического run, ничего не изменяя. */
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const path = process.argv[2] ?? process.env.PRODUCT_DEMO_STATE
if (!path) throw new Error('Передайте путь state.json: node scripts/product_demo_check.mjs /absolute/path/state.json')
const state = JSON.parse(await readFile(path, 'utf8'))
assert.equal(state.synthetic, true)
assert.equal(state.ai_requested, false)
async function call(route, token, body) {
  const response = await fetch(`${state.api}${route}`, {
    method: body ? 'POST' : 'GET',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(body ? { 'Content-Type': 'application/json' } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  })
  assert.ok(response.ok, `${route}: HTTP ${response.status}`)
  return response.json()
}
const tokens = {}
for (const account of state.accounts) {
  const auth = await call('/auth/login', null, { email: account.email, password: account.password })
  tokens[account.key] = auth.access_token
  assert.equal((await call('/auth/me', auth.access_token)).role, 'doctor')
}
const imported = await call(`/archives/imports/${state.imports.completed}`, tokens.coordinator)
assert.equal(imported.status, 'completed')
assert.equal(imported.report_json.ai_requested, false)
assert.equal((await call(`/archives/imports/${state.imports.review}`, tokens.coordinator)).status, 'needs_review')
for (const id of state.records) assert.equal((await call(`/records/${id}`, tokens.coordinator)).attachments.length, 1)
for (const [key, expected] of [['draft', 'draft'], ['active', 'active'], ['complete', 'closed']]) {
  assert.equal((await call(`/cases/${state.cases[key]}`, tokens.coordinator)).status, expected)
}
const opinions = await call(`/cases/${state.cases.active}/opinions`, tokens.colleague)
assert.equal(opinions.items.find(item => item.id === state.opinion)?.status, 'open', 'Вопрос уже расходован; для живого показа создайте новый run')
const complete = await call(`/cases/${state.cases.complete}`, tokens.coordinator)
assert.equal(complete.case.published_record_id, state.published_record)
const conclusions = await call(`/cases/${state.cases.complete}/conclusions`, tokens.coordinator)
assert.equal(conclusions.items[0].summary, state.texts.summary)
console.log(`Готов к показу: ${state.run}; 3 исходных вложения; ручной импорт completed; вопрос open; итог опубликован; AI не запрашивался.`)
