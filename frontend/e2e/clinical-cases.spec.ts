import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const password = 'DemoPass123'
async function login(page: Page, email: string) {
  await page.goto('/auth/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Пароль', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).toHaveURL(/\/dashboard\/doctor$/)
}
async function token(request: APIRequestContext, email: string) {
  const r = await request.post('/api/auth/login', { data: { email, password } })
  expect(r.ok(), await r.text()).toBeTruthy()
  return (await r.json()).access_token as string
}

test('two doctors complete a clinical case and revocation closes an open document', async ({ browser, request }, testInfo) => {
  test.setTimeout(120_000)
  const suffix = `${Date.now()}`
  const ownerToken = await token(request, 'dr.sokolov@docere.demo')
  const peerToken = await token(request, 'dr.kim@docere.demo')
  const adminToken = await token(request, 'admin@docere.demo')
  const ownerHeaders = { Authorization: `Bearer ${ownerToken}` }
  const peerHeaders = { Authorization: `Bearer ${peerToken}` }
  const outsiderEmail = `outsider-${suffix}@cases.example.com`
  const staff = await request.post('/api/admin/users', { headers: { Authorization: `Bearer ${adminToken}` },
    data: { fio: 'Посторонний врач', email: outsiderEmail, phone: '+79999990000', password, role: 'doctor' } })
  expect(staff.ok(), await staff.text()).toBeTruthy()
  const outsiderHeaders = { Authorization: `Bearer ${await token(request, outsiderEmail)}` }
  const patientResponse = await request.post('/api/patients', { headers: ownerHeaders, data: { fio: `Тестовый пациент ${suffix}` } })
  expect(patientResponse.ok(), await patientResponse.text()).toBeTruthy()
  const patient = await patientResponse.json()
  const recordIds: string[] = []
  for (const title of ['Выбранный материал', 'Не включённый материал']) {
    const r = await request.post('/api/records', { headers: ownerHeaders, data: { patient_passport_id: patient.id,
      author_practitioner_full_name: 'Дмитрий Соколов', record_type: 'exam_result', event_date: '2026-09-01',
      title, clinical_summary: 'Синтетический материал для проверки доступа', payload_json: {} } })
    expect(r.ok(), await r.text()).toBeTruthy()
    recordIds.push((await r.json()).id)
  }
  const fileResponse = await request.post(`/api/records/${recordIds[0]}/attachments`, { headers: ownerHeaders,
    multipart: { file: { name: 'synthetic.png', mimeType: 'image/png',
      buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jZ1kAAAAASUVORK5CYII=', 'base64') } } })
  expect(fileResponse.ok(), await fileResponse.text()).toBeTruthy()
  const file = await fileResponse.json()
  const ownerContext = await browser.newContext()
  const peerContext = await browser.newContext()
  const outsiderContext = await browser.newContext()
  const owner = await ownerContext.newPage(), peer = await peerContext.newPage(), outsider = await outsiderContext.newPage()
  try {
    await login(owner, 'dr.sokolov@docere.demo')
    await owner.goto('/cases/new')
    await owner.getByLabel('Найти пациента').fill(`Тестовый пациент ${suffix}`)
    await owner.getByRole('button', { name: 'Найти', exact: true }).click()
    await owner.getByRole('button', { name: new RegExp(`Тестовый пациент ${suffix}`) }).click()
    await owner.getByRole('button', { name: 'Перейти к материалам' }).click()
    await owner.getByRole('checkbox', { name: /Выбранный материал/ }).check()
    await owner.getByRole('button', { name: 'Сформулировать вопрос' }).click()
    await owner.getByLabel('Название', { exact: true }).fill('Совместный тестовый разбор')
    await owner.getByLabel('Вопрос для обсуждения').fill('Секретный клинический вопрос')
    await owner.getByRole('button', { name: 'Создать черновик' }).click()
    await expect(owner).toHaveURL(/\/cases\/[\da-f-]+$/)
    const caseId = owner.url().split('/').at(-1)!
    const caseUrl = `/api/cases/${caseId}`
    owner.setDefaultTimeout(15_000); peer.setDefaultTimeout(15_000); outsider.setDefaultTimeout(15_000)
    await owner.getByRole('button', { name: 'Участники', exact: true }).click()
    await owner.getByLabel('Найти врача').fill('dr.kim@docere.demo')
    await owner.getByRole('button', { name: 'Найти врача', exact: true }).click()
    await owner.getByRole('button', { name: /Пригласить:.*dr.kim/ }).click()
    await expect(owner.getByText(/Приглашён/)).toBeVisible()

    await login(peer, 'dr.kim@docere.demo')
    await peer.goto('/notifications')
    await expect(peer.getByRole('link', { name: /приглашение/i }).first()).toBeVisible()
    await peer.screenshot({ path: testInfo.outputPath('inbox.png'), fullPage: true })
    await peer.locator(`a[href="/cases/${caseId}"]`).click()
    await expect(peer.getByRole('heading', { name: 'Приглашение в разбор' })).toBeVisible()
    await expect(peer.getByText('Секретный клинический вопрос')).toHaveCount(0)
    await expect(peer.getByText(/Координатор сможет добавлять новые материалы/)).toBeVisible()
    await peer.getByRole('button', { name: 'Принять приглашение' }).click()
    await expect(peer.getByText('Секретный клинический вопрос')).toBeVisible()
    await expect(peer.getByText('Не включённый материал')).toHaveCount(0)
    expect([403, 404]).toContain((await request.get(`/api/records/${recordIds[1]}`, { headers: peerHeaders })).status())

    await owner.getByRole('button', { name: 'Совместный разбор', exact: true }).click()
    await owner.getByRole('button', { name: 'Добавить материалы', exact: true }).click()
    await owner.getByRole('checkbox', { name: /Не включённый материал/ }).check()
    await owner.getByRole('button', { name: 'Продолжить добавление' }).click()
    await expect(owner.getByRole('dialog', { name: 'Доступ к новым материалам' }).getByText('Ким Анна Сергеевна')).toBeVisible()
    await owner.getByRole('button', { name: 'Подтвердить добавление материалов' }).click()
    await expect(peer.getByRole('button', { name: /2026-09-01 · Не включённый материал/ })).toBeVisible()

    await login(outsider, outsiderEmail)
    await outsider.goto(`/cases/${caseId}`)
    await expect(outsider.getByText('Секретный клинический вопрос')).toHaveCount(0)
    for (const path of ['', '/messages', '/materials?query=Синтетический', '/conclusions', '/events',
      `/materials/${recordIds[0]}/attachments/${file.id}`]) {
      expect((await request.get(caseUrl + path, { headers: outsiderHeaders })).status()).toBe(404)
    }
    const savedDraft = owner.waitForResponse(response => response.url().endsWith('/work-drafts/message')
      && response.request().method() === 'PUT' && response.ok()
      && response.request().postDataJSON()?.content?.text === 'Личный текст до отправки.')
    await owner.getByLabel('Новое сообщение', { exact: true }).fill('Личный текст до отправки.')
    await savedDraft
    await expect(owner.getByText('Черновик сохранён · только для вас').first()).toBeVisible()
    await owner.getByRole('button', { name: 'Итог', exact: true }).click()
    await owner.getByRole('button', { name: 'Совместный разбор', exact: true }).click()
    await expect(owner.getByLabel('Новое сообщение', { exact: true })).toHaveValue('Личный текст до отправки.')
    await owner.reload()
    await expect(owner.getByLabel('Новое сообщение', { exact: true })).toHaveValue('Личный текст до отправки.')
    await expect(peer.getByText('Личный текст до отправки.')).toHaveCount(0)
    await owner.getByLabel('Новое сообщение', { exact: true }).fill('')
    await owner.getByText('Запросить мнение коллеги', { exact: true }).click()
    await owner.getByLabel('Адресат').selectOption({ label: 'Ким Анна Сергеевна' })
    await owner.getByLabel('Вопрос', { exact: true }).fill('Каково ваше мнение по выбранному материалу?')
    await owner.getByRole('button', { name: 'Запросить мнение', exact: true }).click()
    await peer.goto('/notifications')
    await peer.locator(`a[href^="/cases/${caseId}?"][href*="opinion="]`).click()
    await expect(peer.getByText('Каково ваше мнение по выбранному материалу?', { exact: true })).toBeVisible()
    await peer.getByLabel('Ответ на запрос мнения', { exact: true }).fill('Материал изучен, это тестовый ответ коллеги.')
    await peer.getByRole('button', { name: 'Отправить ответ на запрос' }).click()
    await expect(owner.getByText('Материал изучен, это тестовый ответ коллеги.', { exact: true })).toBeVisible()
    await peer.getByRole('button', { name: /01\/09\/2026 · Выбранный материал/ }).click()
    await peer.getByLabel('Вложение', { exact: true }).selectOption(file.id)
    await expect(peer.getByAltText('Вложение медицинской записи')).toBeVisible()
    await peer.getByRole('button', { name: 'Увеличить изображение' }).click()
    await expect(peer.getByText('125%', { exact: true })).toBeVisible()
    await peer.getByRole('button', { name: 'По размеру панели' }).click()
    await peer.getByRole('button', { name: 'На весь экран', exact: true }).click()
    await expect(peer.getByRole('dialog', { name: 'Просмотр документа' })).toBeVisible()
    await peer.keyboard.press('Escape')
    await expect(peer.getByRole('dialog', { name: 'Просмотр документа' })).toHaveCount(0)
    await expect(peer.getByRole('button', { name: 'На весь экран', exact: true })).toBeFocused()
    await peer.screenshot({ path: testInfo.outputPath('case-document.png') })
    await peer.getByRole('button', { name: 'Сослаться на вложение в сообщении' }).click()
    await peer.getByLabel('Новое сообщение', { exact: true }).fill('Ссылка на тестовое вложение.')
    await peer.getByRole('button', { name: 'Отправить сообщение' }).click()
    await peer.getByRole('button', { name: 'Открыть связанный материал' }).click()
    await expect(peer.getByAltText('Вложение медицинской записи')).toBeVisible()
    await peer.getByRole('button', { name: 'Закрыть просмотр' }).click()

    await owner.getByRole('button', { name: 'Итог', exact: true }).click()
    await owner.getByRole('button', { name: 'Составить новую версию итога' }).click()
    await owner.getByLabel('Краткое резюме').fill('Материалы рассмотрены двумя врачами.')
    await owner.getByLabel('Выводы', { exact: true }).fill('Синтетический итог для проверки процесса.')
    await owner.getByLabel('Дальнейшие действия', { exact: true }).fill('Проверить публикацию в истории.')
    await owner.getByRole('checkbox', { name: /Выбранный материал/ }).check()
    await owner.getByRole('button', { name: 'Сохранить версию итога' }).click()
    await owner.getByRole('button', { name: 'Завершить разбор' }).click()
    await owner.getByRole('button', { name: 'Подтвердить завершение' }).click()
    await expect(peer.getByRole('button', { name: 'Отправить сообщение' })).toHaveCount(0)
    await owner.getByRole('button', { name: 'Предпросмотр публикации в истории' }).click()
    await owner.getByLabel('Дата медицинского события').fill('12.09.2026')
    await owner.getByLabel('Дата медицинского события').press('Tab')
    await owner.getByRole('button', { name: 'Опубликовать в истории', exact: true }).click()
    await expect(owner.getByText('Итог опубликован как самостоятельная запись.', { exact: false })).toBeVisible()
    await owner.screenshot({ path: testInfo.outputPath('case-published.png'), fullPage: true })
    await owner.getByRole('link', { name: 'Открыть опубликованную запись' }).click()
    await expect(owner.getByRole('heading', { name: /Совместный разбор/ }).last()).toBeVisible()
    await owner.goto(`/cases/${caseId}?tab=conclusion`)
    for (const width of [390, 768, 1440]) {
      await owner.setViewportSize({ width, height: 900 })
      await expect(owner.getByText('Итог опубликован как самостоятельная запись.', { exact: false })).toBeVisible()
      expect(await owner.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
      await owner.screenshot({ path: testInfo.outputPath(`conclusion-${width}.png`), fullPage: true })
    }
    const view = await (await request.get(caseUrl, { headers: ownerHeaders })).json()
    const publishedId = view.case.published_record_id
    const published = await (await request.get(`/api/records/${publishedId}`, { headers: ownerHeaders })).json()
    expect(published.event_date).toBe('2026-09-12')
    expect(published.status).toBe('unconfirmed')
    expect(published.payload_json.case_provenance.case_id).toBe(caseId)
    expect(published.payload_json.case_provenance.source_record_ids).toEqual([recordIds[0]])
    expect([403, 404]).toContain((await request.get(`/api/records/${publishedId}`, { headers: peerHeaders })).status())
    expect((await request.post(caseUrl + '/publish', { headers: ownerHeaders, data: { event_date: '2026-09-12' } })).ok()).toBeTruthy()
    const repeated = await (await request.get(caseUrl, { headers: ownerHeaders })).json()
    expect(repeated.case.published_record_id).toBe(publishedId)
    await peer.getByRole('button', { name: /01\/09\/2026 · Выбранный материал/ }).click()
    await peer.getByLabel('Вложение', { exact: true }).selectOption(file.id)
    await expect(peer.getByAltText('Вложение медицинской записи')).toBeVisible()
    await owner.getByRole('button', { name: 'Участники', exact: true }).click()
    await owner.getByRole('button', { name: 'Исключить', exact: true }).click()
    await expect(peer.getByRole('dialog', { name: 'Материал случая' })).toHaveCount(0)
    await expect(peer.getByText('Секретный клинический вопрос')).toHaveCount(0)
    expect((await request.get(caseUrl + `/materials/${recordIds[0]}/attachments/${file.id}`, { headers: peerHeaders })).status()).toBe(404)
  } finally { await Promise.allSettled([ownerContext.close(), peerContext.close(), outsiderContext.close()]) }
})
