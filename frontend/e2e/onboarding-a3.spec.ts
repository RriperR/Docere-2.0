import { randomUUID } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const password = 'DemoPass123'
const adminEmail = process.env.ONBOARDING_ADMIN_EMAIL ?? 'admin@docere.demo'
const adminPassword = process.env.ONBOARDING_ADMIN_PASSWORD ?? password

async function token(request: APIRequestContext, email: string, secret = password) {
  const response = await request.post('/api/auth/login', { data: { email, password: secret } })
  expect(response.ok()).toBeTruthy()
  return (await response.json()).access_token as string
}

async function sessionToken(page: Page) {
  return page.evaluate(() => JSON.parse(localStorage.getItem('authTokens')!).access_token as string)
}

async function register(page: Page, email: string, name: string) {
  await page.goto('/auth/register')
  await page.getByLabel('Фамилия *', { exact: true }).fill('Синтетический')
  await page.getByLabel('Имя *', { exact: true }).fill(name)
  await page.getByLabel('Email *', { exact: true }).fill(email)
  await page.getByLabel('Телефон *', { exact: true }).fill('+79990000001')
  await page.getByLabel('Пароль *', { exact: true }).fill(password)
  await page.getByLabel('Подтвердите пароль *', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Зарегистрироваться' }).click()
  await expect(page).toHaveURL(/\/dashboard\/patient$/)
  await expect(page.getByText('Записей пока нет', { exact: true }).first()).toBeVisible()
}

async function login(page: Page, email: string, role: 'patient' | 'doctor') {
  await page.goto('/auth/login')
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Пароль', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`/dashboard/${role}$`))
}

async function apply(page: Page) {
  await page.goto('/doctor-role-request')
  await page.getByLabel('Специализация', { exact: true }).fill('Кардиология')
  await page.getByRole('checkbox', { name: new RegExp(adminEmail.replaceAll('.', '\\.')) }).check()
  const submitted = page.waitForResponse(r => r.url().endsWith('/api/doctor-role-applications') && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Отправить на проверку' }).click()
  const response = await submitted
  expect(response.ok()).toBeTruthy()
  await expect(page.getByText('На проверке', { exact: true }).first()).toBeVisible()
  return (await response.json()).id as string
}

async function approve(request: APIRequestContext, adminToken: string, id: string) {
  const response = await request.post(`/api/doctor-role-applications/${id}/review`, {
    headers: { Authorization: `Bearer ${adminToken}` }, data: { decision: 'approved', note: 'Синтетическая проверка A1' },
  })
  expect(response.ok()).toBeTruthy()
  expect((await response.json()).status).toBe('approved')
}

async function share(page: Page, patientId: string, recipient: string) {
  await page.goto(`/patients/${patientId}`)
  await page.locator('input[type=checkbox]').first().check()
  await page.getByRole('button', { name: 'Поделиться (1)', exact: true }).click()
  await page.getByPlaceholder('email или ФИО получателя').fill(recipient)
  await page.getByRole('button', { name: 'Отправить запрос', exact: true }).click()
  await expect(page.getByText('Приглашение к записям создано: отправлено 1 записей.')).toBeVisible()
}

async function accept(page: Page) {
  await page.goto('/share-requests')
  const accepted = page.waitForResponse(response => /\/api\/share-requests\/[^/]+\/accept$/.test(response.url()) && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Принять', exact: true }).click()
  expect((await accepted).ok()).toBeTruthy()
  await expect(page.getByRole('button', { name: 'Принять', exact: true })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Открыть карточку', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Открыть карточку', exact: true }).click()
}

test('A3: card → manual import → record → explicit case selection, accepted patient transfer and denied IDs', async ({ browser, page, request, baseURL }) => {
  test.setTimeout(240_000)
  page.setDefaultTimeout(15_000)
  const run = randomUUID()
  const emails = Object.fromEntries(['patient', 'doctor', 'second', 'outsider'].map(role => [role, `a3-${role}-${run}@example.com`]))
  const adminToken = await token(request, adminEmail, adminPassword)
  const contexts = await Promise.all(Array.from({ length: 3 }, () => browser.newContext({ baseURL })))
  const [patientPage, secondPage, outsiderPage] = await Promise.all(contexts.map(context => context.newPage()))
  for (const actor of [patientPage, secondPage, outsiderPage]) actor.setDefaultTimeout(15_000)
  try {
    await register(patientPage, emails.patient, 'Пациент')
    await register(secondPage, emails.second, 'Второй')
    await approve(request, adminToken, await apply(secondPage))
    await secondPage.getByRole('button', { name: 'Выйти', exact: true }).first().click()
    await login(secondPage, emails.second, 'doctor')
    await register(outsiderPage, emails.outsider, 'Посторонний')
    const outsiderToken = await sessionToken(outsiderPage)
    const foreignCards = await request.get('/api/patients', { headers: { Authorization: `Bearer ${outsiderToken}` } })
    const foreignId = (await foreignCards.json())[0].id as string
    await register(page, emails.doctor, 'Первый')
    await approve(request, adminToken, await apply(page))
    await page.getByRole('button', { name: 'Выйти', exact: true }).first().click()
    await login(page, emails.doctor, 'doctor')
    await page.getByRole('link', { name: 'Добавить пациента', exact: true }).first().click()
    await page.getByLabel('Фамилия *', { exact: true }).fill('Синтетический')
    await page.getByLabel('Имя *', { exact: true }).fill(`Пациент ${run}`)
    await page.getByLabel('Email', { exact: true }).fill(emails.patient)
    const created = page.waitForResponse(r => r.url().endsWith('/api/patients') && r.request().method() === 'POST')
    await page.getByRole('button', { name: 'Создать', exact: true }).click()
    const patientResponse = await created
    expect(patientResponse.ok()).toBeTruthy()
    const patientId = (await patientResponse.json()).id as string
    await page.getByRole('row', { name: new RegExp(`Синтетический Пациент ${run}`) }).getByRole('link', { name: 'Открыть →' }).click()
    await expect(page.getByRole('button', { name: '+ Добавить запись' })).toBeVisible()
    await page.getByRole('main').getByRole('link', { name: 'Импорт документов', exact: true }).click()
    await expect(page).toHaveURL(new URL(`/upload?patient=${patientId}`, baseURL).href)
    await expect(page.getByText(new RegExp('Импорт для пациента: Синтетический Пациент'))).toBeVisible()
    await page.locator('input[type=file]').setInputFiles({ name: `a3-${run}.png`, mimeType: 'image/png', buffer: readFileSync(resolve(process.cwd(), '../tests/fixtures/import_ai/synthetic-scan.png')) })
    await expect(page.getByRole('checkbox', { name: 'Проанализировать с AI' })).not.toBeChecked()
    await page.getByRole('button', { name: 'Загрузить', exact: true }).click()
    await expect(page).toHaveURL(/\/upload\/status\//)
    const jobId = new URL(page.url()).pathname.split('/').at(-1)!
    await page.getByRole('button', { name: 'Проверить импорт', exact: true }).click({ timeout: 90_000 })
    await expect(page.getByRole('combobox', { name: 'Решение', exact: true })).toHaveValue('create')
    await page.getByRole('button', { name: new RegExp(`Выбрать Синтетический Пациент ${run} для этих документов`) }).click()
    await expect(page.getByRole('combobox', { name: 'Карточка пациента' })).toHaveValue(patientId)
    const title = `Синтетический документ A3 ${run}`
    await page.getByRole('textbox', { name: 'Название', exact: true }).fill(title)
    await page.getByRole('textbox', { name: 'Дата события', exact: true }).fill('13.10.2026')
    await page.keyboard.press('Tab'); await page.keyboard.press('Escape')
    await expect(page.getByText('Требуют решения: 0')).toBeVisible()
    await expect(page.getByText(/Черновик сохранён/)).toBeVisible()
    const draftResponse = await request.get(`/api/archives/imports/${jobId}`, { headers: { Authorization: `Bearer ${await sessionToken(page)}` } })
    const draft = await draftResponse.json()
    const forbiddenPatient = await request.post(`/api/archives/imports/${jobId}/resolve`, { headers: { Authorization: `Bearer ${await sessionToken(page)}` }, data: {
      version: draft.version, decisions: draft.review_decisions.map((decision: Record<string, unknown>) => ({ ...decision, action: 'existing', patient_passport_id: foreignId })),
    } })
    expect(forbiddenPatient.status()).toBe(422)
    expect((await (await request.get(`/api/archives/imports/${jobId}`, { headers: { Authorization: `Bearer ${await sessionToken(page)}` } })).json()).status).toBe('needs_review')
    await page.route(`**/api/archives/imports/${jobId}/resolve`, route => route.abort('failed'), { times: 1 })
    page.once('dialog', dialog => void dialog.accept())
    await page.getByRole('button', { name: 'Подтвердить импорт', exact: true }).click()
    await expect(page.getByText('Не удалось подтвердить импорт. Проверьте соединение и повторите. Ваши решения остались в форме.', { exact: true })).toBeVisible()
    await expect(page.getByRole('textbox', { name: 'Название', exact: true })).toHaveValue(title)
    await expect(page.getByRole('combobox', { name: 'Карточка пациента' })).toHaveValue(patientId)
    await page.reload()
    await expect(page.getByRole('textbox', { name: 'Название', exact: true })).toHaveValue(title)
    await expect(page.getByRole('combobox', { name: 'Карточка пациента' })).toHaveValue(patientId)
    page.once('dialog', dialog => void dialog.accept())
    await page.getByRole('button', { name: 'Подтвердить импорт', exact: true }).click()
    await expect(page.getByText('Результат импорта', { exact: true })).toBeVisible()
    const ownerToken = await sessionToken(page)
    const job = await (await request.get(`/api/archives/imports/${jobId}`, { headers: { Authorization: `Bearer ${ownerToken}` } })).json()
    const recordId = job.report_json.resolved_patients[0].record_ids[0] as string
    expect(job.report_json.ai_requested).toBe(false)
    await page.getByRole('link', { name: /^Открыть запись 1/ }).click()
    await expect(page).toHaveURL(new RegExp(`/patients/${patientId}#record-${recordId}`))
    await expect(page.getByText(title, { exact: true }).first()).toBeVisible()
    await page.locator('input[type=checkbox]').first().check()
    await page.getByRole('link', { name: 'Обсудить записи (1)', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Перейти к материалам' })).toBeEnabled()
    await page.getByRole('button', { name: 'Перейти к материалам' }).click()
    await expect(page.getByRole('checkbox', { name: new RegExp(title) })).toBeChecked()
    await page.getByRole('checkbox', { name: new RegExp(title) }).uncheck()
    await expect(page.getByText('Выбрано: 0 из 1 доступных · максимум 100')).toBeVisible()
    await page.getByRole('checkbox', { name: new RegExp(title) }).check()
    await page.getByRole('button', { name: 'Сформулировать вопрос' }).click()
    await page.getByLabel('Название', { exact: true }).fill('Синтетический разбор A3')
    await page.getByLabel('Вопрос для обсуждения').fill('Какие сведения нужны перед следующим приёмом?')
    await page.getByRole('button', { name: 'Создать черновик' }).click()
    await expect(page).toHaveURL(/\/cases\/[^/]+$/)
    await share(page, patientId, emails.patient)
    const patientToken = await sessionToken(patientPage), secondToken = await sessionToken(secondPage)
    for (const bearer of [patientToken, secondToken, outsiderToken]) expect((await request.get(`/api/records/${recordId}`, { headers: { Authorization: `Bearer ${bearer}` } })).status()).toBe(403)
    await patientPage.goto('/dashboard/patient')
    await expect(patientPage.getByText(title, { exact: true })).toHaveCount(0)
    await accept(patientPage)
    await patientPage.goto('/dashboard/patient')
    await expect(patientPage.getByRole('heading', { name: 'Принятые материалы' })).toBeVisible()
    await patientPage.getByRole('link', { name: new RegExp(title) }).click()
    await patientPage.getByRole('button', { name: new RegExp(`a3-${run}\\.png`) }).click()
    await expect(patientPage.getByAltText('Вложение медицинской записи')).toBeVisible()
    await share(patientPage, patientId, emails.second)
    expect((await request.get(`/api/records/${recordId}`, { headers: { Authorization: `Bearer ${secondToken}` } })).status()).toBe(403)
    await accept(secondPage)
    expect((await request.get(`/api/records/${recordId}`, { headers: { Authorization: `Bearer ${secondToken}` } })).status()).toBe(200)
    expect((await request.get(`/api/records/${recordId}`, { headers: { Authorization: `Bearer ${outsiderToken}` } })).status()).toBe(403)
    expect((await request.get(`/api/patients/${patientId}`, { headers: { Authorization: `Bearer ${outsiderToken}` } })).status()).toBe(404)
    await secondPage.getByRole('button', { name: 'Выйти', exact: true }).first().click()
    await login(secondPage, emails.second, 'doctor')
    await page.goto(`/upload?patient=${foreignId}`)
    await expect(page.getByText('Карточка из ссылки недоступна. Проверьте права доступа или продолжите без неё.')).toBeVisible()
    await expect(page.getByText(/Импорт для пациента:/)).toHaveCount(0)
    const resolveDenied = await request.post(`/api/archives/imports/${jobId}/resolve`, { headers: { Authorization: `Bearer ${outsiderToken}` }, data: { decisions: draft.review_decisions, version: draft.version } })
    expect(resolveDenied.status()).toBe(403)
  } finally { await Promise.all(contexts.map(context => context.close())) }
})
