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
  await page.getByRole('button', { name: 'Принять', exact: true }).click()
  await expect(page.getByRole('link', { name: 'Открыть карточку', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Открыть карточку', exact: true }).click()
}

test('A1: new doctor registers, imports without AI and shares through a new patient to another doctor', async ({ browser, page, request, baseURL }) => {
  test.setTimeout(240_000)
  page.setDefaultTimeout(15_000)
  const run = randomUUID()
  const emails = Object.fromEntries(['patient', 'pending', 'doctor', 'second', 'outsider'].map(role => [role, `a1-${role}-${run}@example.com`]))
  const adminToken = await token(request, adminEmail, adminPassword)
  const contexts = await Promise.all(Array.from({ length: 4 }, () => browser.newContext({ baseURL })))
  const [patientPage, pendingPage, secondPage, outsiderPage] = await Promise.all(contexts.map(context => context.newPage()))
  for (const actorPage of [patientPage, pendingPage, secondPage, outsiderPage]) actorPage.setDefaultTimeout(15_000)
  try {
    await register(patientPage, emails.patient, 'Пациент')
    await register(pendingPage, emails.pending, 'Ожидающий')
    await apply(pendingPage)
    await register(secondPage, emails.second, 'Второй')
    await approve(request, adminToken, await apply(secondPage))
    await secondPage.getByRole('button', { name: 'Меню аккаунта', exact: true }).click()
    await secondPage.getByRole('button', { name: 'Выйти', exact: true }).click()
    await login(secondPage, emails.second, 'doctor')
    await register(outsiderPage, emails.outsider, 'Посторонний')
    await register(page, emails.doctor, 'Первый')
    await approve(request, adminToken, await apply(page))
    await page.getByRole('button', { name: 'Меню аккаунта', exact: true }).click()
    await page.getByRole('button', { name: 'Выйти', exact: true }).click()
    await login(page, emails.doctor, 'doctor')
    await expect(page.getByRole('link', { name: /Синтетический Первый Записей: 0/ })).toBeVisible()

    await page.goto('/patients')
    await page.getByRole('button', { name: 'Добавить пациента', exact: true }).click()
    await page.getByText('Фамилия *', { exact: true }).locator('..').locator('input').fill('Синтетический')
    await page.getByText('Имя *', { exact: true }).locator('..').locator('input').fill(`Пациент ${run}`)
    await page.getByText('Email', { exact: true }).locator('..').locator('input').fill(emails.patient)
    const created = page.waitForResponse(r => r.url().endsWith('/api/patients') && r.request().method() === 'POST')
    await page.getByRole('button', { name: 'Создать', exact: true }).click()
    const patientResponse = await created
    expect(patientResponse.ok()).toBeTruthy()
    const patientId = (await patientResponse.json()).id as string

    await page.goto('/upload')
    await page.locator('input[type=file]').setInputFiles({
      name: `a1-${run}.png`, mimeType: 'image/png',
      buffer: readFileSync(resolve(process.cwd(), '../tests/fixtures/import_ai/synthetic-scan.png')),
    })
    await expect(page.getByRole('checkbox', { name: 'Проанализировать с AI' })).not.toBeChecked()
    await page.getByRole('button', { name: 'Загрузить', exact: true }).click()
    await expect(page).toHaveURL(/\/upload\/status\//)
    const jobId = page.url().split('/').at(-1)!
    await page.getByRole('button', { name: 'Проверить документы', exact: true }).click({ timeout: 90_000 })
    await page.getByRole('combobox', { name: 'Решение', exact: true }).selectOption('existing')
    await page.getByRole('combobox', { name: 'Карточка пациента', exact: true }).selectOption(patientId)
    const title = `Синтетический документ A1 ${run}`
    await page.getByRole('textbox', { name: 'Название', exact: true }).fill(title)
    await page.getByRole('textbox', { name: 'Дата события', exact: true }).fill('12.10.2026')
    await page.keyboard.press('Tab')
    await page.keyboard.press('Escape')
    for (const checkbox of await page.getByRole('checkbox', { name: 'Я проверил, что документ относится к выбранному пациенту' }).all()) await checkbox.check()
    await expect(page.getByText('Нужны данные: 0 документов', { exact: true })).toBeVisible()
    page.once('dialog', dialog => void dialog.accept())
    await page.getByRole('button', { name: 'Сохранить 1 записей в историю', exact: true }).click()
    await expect(page.getByText('Результат импорта', { exact: true })).toBeVisible()
    await page.getByRole('link', { name: 'Открыть медицинскую историю', exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`/patients/${patientId}`))
    await page.getByRole('button', { name: new RegExp(`a1-${run}\\.png`) }).click()
    await expect(page.getByAltText('Вложение медицинской записи')).toBeVisible()
    const ownerToken = await sessionToken(page)
    const job = await (await request.get(`/api/archives/imports/${jobId}`, { headers: { Authorization: `Bearer ${ownerToken}` } })).json()
    const recordId = job.report_json.resolved_patients[0].record_ids[0] as string
    expect(job.status).toBe('completed')

    const patientToken = await sessionToken(patientPage)
    const secondToken = await sessionToken(secondPage)
    for (const bearer of [patientToken, secondToken, await sessionToken(outsiderPage)]) {
      expect((await request.get(`/api/records/${recordId}`, { headers: { Authorization: `Bearer ${bearer}` } })).status()).toBe(403)
    }
    await share(page, patientId, emails.patient)
    expect((await request.get(`/api/records/${recordId}`, { headers: { Authorization: `Bearer ${patientToken}` } })).status()).toBe(403)
    await accept(patientPage)
    await expect(patientPage.getByText(title, { exact: true }).first()).toBeVisible()
    // Dashboard currently selects the patient's own empty card after a full navigation;
    // accepted shared records remain readable from the invitation's patient card (A3 baseline).
    await share(patientPage, patientId, emails.second)
    expect((await request.get(`/api/records/${recordId}`, { headers: { Authorization: `Bearer ${secondToken}` } })).status()).toBe(403)
    await accept(secondPage)
    await expect(secondPage.getByText(title, { exact: true }).first()).toBeVisible()
    await secondPage.goto(`/patients/${patientId}?record=${recordId}`)
    await secondPage.getByRole('button', { name: new RegExp(`a1-${run}\\.png`) }).click()
    await expect(secondPage.getByAltText('Вложение медицинской записи')).toBeVisible()
    expect((await request.get(`/api/records/${recordId}`, { headers: { Authorization: `Bearer ${await sessionToken(outsiderPage)}` } })).status()).toBe(403)
    await pendingPage.reload()
    await expect(pendingPage.getByText('На проверке', { exact: true }).first()).toBeVisible()
  } finally {
    await Promise.all(contexts.map(context => context.close()))
  }
})
