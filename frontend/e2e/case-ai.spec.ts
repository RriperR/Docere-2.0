import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const password = 'DemoPass123'
async function token(request: APIRequestContext, email: string) {
  const response = await request.post('/api/auth/login', { data: { email, password } })
  expect(response.ok(), await response.text()).toBeTruthy()
  return (await response.json()).access_token as string
}
async function login(page: Page, email: string) {
  await page.goto('/auth/login')
  await page.getByLabel('Email').fill(email); await page.getByLabel('Пароль', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Войти', exact: true }).click(); await page.waitForURL('**/dashboard/doctor')
}

// Explicit opt-in: this scenario sends only synthetic fixture documents to the configured real provider.
test('real AI summary sources, two doctors, publication and revoked access', async ({ browser, request }, testInfo) => {
  test.skip(process.env.DOCERE_REAL_AI_E2E !== '1', 'Explicit opt-in required for calls to the real provider')
  test.setTimeout(300_000)
  const ownerHeaders = { Authorization: `Bearer ${await token(request, 'dr.sokolov@docere.demo')}` }
  const peerHeaders = { Authorization: `Bearer ${await token(request, 'dr.kim@docere.demo')}` }
  const peerIdentity = await request.get('/api/auth/me', { headers: peerHeaders })
  expect(peerIdentity.ok()).toBeTruthy()
  const peerId = (await peerIdentity.json()).id
  const adminHeaders = { Authorization: `Bearer ${await token(request, 'admin@docere.demo')}` }
  const outsiderEmail = `ai-outsider-${Date.now()}@cases.example.com`
  const staff = await request.post('/api/admin/users', { headers: adminHeaders,
    data: { fio: 'Синтетический посторонний врач', email: outsiderEmail, phone: '+79999990000', password, role: 'doctor' } })
  expect(staff.ok(), await staff.text()).toBeTruthy()
  const outsiderHeaders = { Authorization: `Bearer ${await token(request, outsiderEmail)}` }
  const patientResponse = await request.post('/api/patients', { headers: ownerHeaders, data: { fio: `Синтетический пациент сводки ${Date.now()}` } })
  expect(patientResponse.ok(), await patientResponse.text()).toBeTruthy()
  const patient = await patientResponse.json()
  const ids: string[] = []
  for (const [title, filename, mimeType] of [
    ['Выбранный синтетический скан', 'synthetic-scan.png', 'image/png'],
    ['Выбранный синтетический PDF', 'synthetic-report.pdf', 'application/pdf'],
  ]) {
    const record = await request.post('/api/records', { headers: ownerHeaders, data: { patient_passport_id: patient.id,
      author_practitioner_full_name: 'Дмитрий Соколов', record_type: 'exam_result', event_date: '2026-10-11',
      title, clinical_summary: 'Синтетический документ для сквозной проверки', payload_json: {} } })
    expect(record.ok(), await record.text()).toBeTruthy()
    const rid = (await record.json()).id; ids.push(rid)
    const file = await request.post(`/api/records/${rid}/attachments`, { headers: ownerHeaders,
      multipart: { file: { name: filename, mimeType, buffer: readFileSync(resolve('..', 'tests/fixtures/import_ai', filename)) } } })
    expect(file.ok(), await file.text()).toBeTruthy()
  }
  const created = await request.post('/api/cases', { headers: ownerHeaders, data: { patient_id: patient.id,
    title: 'AI: сверка документов перед совместным разбором', question: 'Сверим исходники и обсудим факты.', record_ids: ids } })
  expect(created.ok(), await created.text()).toBeTruthy()
  let view = await created.json()
  const cid = view.id; const url = `/api/cases/${cid}`
  const invitation = await request.post(`${url}/invitations`, { headers: ownerHeaders, data: { version: view.case.version, user_id: peerId } })
  expect(invitation.ok(), await invitation.text()).toBeTruthy()
  expect((await request.get(`${url}/ai-summary`, { headers: peerHeaders })).status()).toBe(403)
  expect((await request.get(`${url}/ai-summary`, { headers: outsiderHeaders })).status()).toBe(404)
  const accepted = await request.post(`${url}/invitations/accept`, { headers: peerHeaders })
  expect(accepted.ok(), await accepted.text()).toBeTruthy()
  const ownerContext = await browser.newContext(), peerContext = await browser.newContext()
  const owner = await ownerContext.newPage(), peer = await peerContext.newPage()
  owner.setDefaultTimeout(20_000); peer.setDefaultTimeout(20_000)
  try {
    await login(owner, 'dr.sokolov@docere.demo'); await owner.goto(`/cases/${cid}?tab=summary`)
    const panel = owner.getByRole('region', { name: 'AI-сводка материалов' })
    await expect(panel.getByRole('checkbox', { name: /Выбранный синтетический скан/ })).toBeVisible()
    await expect(panel.getByRole('checkbox').last()).not.toBeChecked()
    for (const box of await panel.getByRole('checkbox', { name: /Выбранный синтетический/ }).all()) await box.check()
    await panel.getByRole('checkbox', { name: /Разрешаю отправить/ }).check()
    await panel.getByRole('button', { name: 'Составить сводку материалов · AI' }).click()
    await expect(panel.getByRole('status')).toContainText('Сводка готова ·', { timeout: 180_000 })
    const run = await (await request.get(`${url}/ai-summary`, { headers: ownerHeaders })).json()
    expect(run.status).toBe('completed'); expect(run.documents).toHaveLength(2)
    expect(run.documents.every((d: { facts: unknown[]; checksum: string }) => d.facts.length && d.checksum)).toBeTruthy()
    expect((await request.get(`${url}/ai-summary/runs/${run.id}`, { headers: peerHeaders })).status()).toBe(404)
    await panel.locator('article').filter({ hasText: 'synthetic-scan.png' }).getByRole('button', { name: /^Стр\./ }).first().click()
    await expect(owner.getByAltText('Вложение медицинской записи')).toBeVisible()
    await expect(owner).toHaveURL(/tab=summary.*page=1/)
    await owner.reload(); await expect(panel.getByRole('status')).toContainText('Сводка готова ·')
    await expect(owner.getByAltText('Вложение медицинской записи')).toBeVisible()
    for (const width of [1440, 768, 390]) {
      await owner.setViewportSize({ width, height: 1000 })
      if (width < 1024) await owner.getByRole('button', { name: 'Сводка', exact: true }).click()
      if (width === 390) {
        await panel.locator('article').filter({ hasText: 'synthetic-scan.png' }).getByRole('button', { name: /^Стр\./ }).first().click()
        await expect(owner.getByAltText('Вложение медицинской записи')).toBeVisible()
        await owner.getByRole('button', { name: 'Сводка', exact: true }).click()
        await expect(panel.getByRole('status')).toContainText('Сводка готова ·')
      }
      expect(await owner.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
      await owner.screenshot({ path: testInfo.outputPath(`summary-${width}.png`), fullPage: true })
    }
    await owner.setViewportSize({ width: 1440, height: 1000 })
    await login(peer, 'dr.kim@docere.demo'); await peer.goto(`/cases/${cid}?tab=summary`)
    const peerPanel = peer.getByRole('region', { name: 'AI-сводка материалов' })
    await peerPanel.getByRole('checkbox', { name: /Выбранный синтетический скан/ }).check()
    await peerPanel.getByRole('checkbox', { name: /Разрешаю отправить/ }).check()
    await peerPanel.getByRole('button', { name: 'Составить сводку материалов · AI' }).click()
    await expect(peerPanel.getByRole('status')).toContainText('Сводка готова ·', { timeout: 120_000 })
    await peerPanel.getByRole('button', { name: /^Стр\./ }).first().click()
    await expect(peer.getByAltText('Вложение медицинской записи')).toBeVisible()
    await peer.getByRole('button', { name: 'Сослаться на вложение в сообщении' }).click()
    await peer.getByLabel('Новое сообщение', { exact: true }).fill('Сверила AI-факты с оригиналом. Это синтетический тестовый ответ.')
    await peer.getByRole('button', { name: 'Отправить сообщение' }).click()
    await owner.getByRole('button', { name: 'Совместный разбор', exact: true }).click()
    await expect(owner.getByText('Сверила AI-факты с оригиналом. Это синтетический тестовый ответ.', { exact: true })).toBeVisible()
    await owner.getByRole('button', { name: 'Итог', exact: true }).click()
    await owner.getByRole('button', { name: 'Составить новую версию итога' }).click()
    await owner.getByLabel('Краткое резюме').fill('Два врача сверили синтетические документы с AI-сводкой.')
    await owner.getByLabel('Выводы', { exact: true }).fill('Проверен процесс работы с источниками; медицинских выводов в тесте нет.')
    await owner.getByLabel('Дальнейшие действия', { exact: true }).fill('Завершить проверку публикации и отзыва доступа.')
    for (const box of await owner.getByRole('checkbox', { name: /Выбранный синтетический/ }).all()) await box.check()
    await owner.getByRole('button', { name: 'Сохранить версию итога' }).click()
    await owner.getByRole('button', { name: 'Завершить разбор' }).click()
    await owner.getByRole('button', { name: 'Подтвердить завершение' }).click()
    await owner.getByRole('button', { name: 'Предпросмотр публикации в истории' }).click()
    await owner.getByLabel('Дата медицинского события').fill('10.10.2026')
    await owner.getByLabel('Дата медицинского события').press('Tab')
    await owner.getByRole('button', { name: 'Опубликовать в истории', exact: true }).click()
    await expect(owner.getByRole('link', { name: 'Открыть опубликованную запись' })).toBeVisible()
    view = await (await request.get(url, { headers: ownerHeaders })).json()
    const published = await (await request.get(`/api/records/${view.case.published_record_id}`, { headers: ownerHeaders })).json()
    expect(published.status).toBe('unconfirmed'); expect(published.event_date).toBe('2026-10-10')
    const repeated = await request.post(`${url}/publish`, { headers: ownerHeaders, data: { event_date: '2026-10-10' } })
    expect((await repeated.json()).record_id).toBe(view.case.published_record_id)
    await peer.getByRole('button', { name: 'AI-сводка', exact: true }).click()
    await peerPanel.getByRole('button', { name: /^Стр\./ }).first().click()
    await expect(peer.getByAltText('Вложение медицинской записи')).toBeVisible()
    const removed = await request.post(`${url}/members/${peerId}/remove`, { headers: ownerHeaders })
    expect(removed.ok(), await removed.text()).toBeTruthy()
    await expect(peer.getByAltText('Вложение медицинской записи')).toHaveCount(0)
    await expect(peer.getByRole('region', { name: 'AI-сводка материалов' })).toHaveCount(0)
    expect((await request.get(`${url}/ai-summary`, { headers: peerHeaders })).status()).toBe(404)
    await owner.getByRole('link', { name: 'Открыть опубликованную запись' }).click()
    await expect(owner.getByRole('heading', { name: /Совместный разбор/ }).last()).toBeVisible()
  } finally { await ownerContext.close(); await peerContext.close() }
})
