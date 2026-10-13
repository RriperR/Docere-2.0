import { randomUUID } from 'node:crypto'
import { expect, test, type Page } from '@playwright/test'

const password = 'DemoPass123'
async function register(page: Page, email: string) {
  await page.goto('/auth/register')
  await page.getByLabel('Фамилия *', { exact: true }).fill('Синтетический')
  await page.getByLabel('Имя *', { exact: true }).fill('Врач A2')
  await page.getByLabel('Email *', { exact: true }).fill(email)
  await page.getByLabel('Телефон *', { exact: true }).fill('+79990000001')
  await page.getByLabel('Пароль *', { exact: true }).fill(password)
  await page.getByLabel('Подтвердите пароль *', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Зарегистрироваться' }).click()
  await expect(page).toHaveURL(/\/dashboard\/patient$/)
}
async function apply(page: Page) {
  await page.getByLabel('Специализация', { exact: true }).fill('Кардиология')
  await page.getByRole('checkbox', { name: /admin@docere.demo/ }).check()
  const submitted = page.waitForResponse(r => r.url().endsWith('/api/doctor-role-applications') && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Отправить на проверку' }).click()
  const response = await submitted
  expect(response.ok()).toBeTruthy()
  await expect(page.getByText('На проверке', { exact: true }).first()).toBeVisible()
  return (await response.json()).id as string
}
async function tabTo(page: Page, name: string, role: 'button' | 'link' = 'link') {
  const target = page.getByRole(role, { name, exact: true }).first()
  for (let i = 0; i < 60; i++) {
    await page.keyboard.press('Tab')
    if (await target.evaluate(element => element === document.activeElement)) return target
  }
  throw new Error(`Keyboard focus did not reach ${name}`)
}
async function noOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true)
}

test('A2: first entry, rejected/pending/approved lifecycle, keyboard creation and responsive dashboards', async ({ page, request, browser }) => {
  test.setTimeout(180_000)
  page.setDefaultTimeout(15_000)
  const admin = await request.post('/api/auth/login', { data: { email: process.env.ONBOARDING_ADMIN_EMAIL ?? 'admin@docere.demo', password: process.env.ONBOARDING_ADMIN_PASSWORD ?? password } })
  expect(admin.ok()).toBeTruthy()
  const adminToken = (await admin.json()).access_token as string
  const review = async (id: string, decision: 'approved' | 'rejected') => {
    const response = await request.post(`/api/doctor-role-applications/${id}/review`, { headers: { Authorization: `Bearer ${adminToken}` }, data: { decision, note: decision === 'rejected' ? 'Синтетический отказ: уточните данные' : 'Синтетическая проверка A2' } })
    expect(response.ok()).toBeTruthy()
  }
  await register(page, `a2-${randomUUID()}@example.com`)
  await expect(page.getByRole('link', { name: 'Я врач', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Открыть карточку', exact: true })).toBeVisible()
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    await noOverflow(page)
  }
  await tabTo(page, 'Я врач')
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/doctor-role-request$/)
  await review(await apply(page), 'rejected')
  await page.goto('/dashboard/patient')
  await expect(page.getByRole('heading', { name: 'Заявка на роль врача отклонена' })).toBeVisible()
  await expect(page.getByText(/Синтетический отказ: уточните данные/)).toBeVisible()
  await page.getByRole('link', { name: 'Уточнить данные заявки' }).click()
  await expect(page.getByText(/Синтетический отказ: уточните данные/)).toBeVisible()
  const second = await apply(page)
  await page.goto('/dashboard/patient')
  await expect(page.getByRole('heading', { name: 'Заявка на роль врача на проверке' })).toBeVisible()
  await page.getByRole('link', { name: 'Посмотреть заявку' }).click()
  await expect(page.getByRole('button', { name: 'Отправить на проверку' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Обновить статус заявки' }).click()
  await expect(page.getByText('Текущая заявка')).toBeVisible()
  await review(second, 'approved')
  await page.reload()
  await expect(page).toHaveURL(/\/dashboard\/doctor$/)
  const add = page.getByRole('link', { name: 'Добавить пациента', exact: true }).first()
  await expect(add).toBeVisible()
  await expect(page.locator('main').getByRole('link', { name: 'Импорт документов', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: /Синтетический Врач A2 Записей: 0/ })).toBeVisible()
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    await noOverflow(page)
    if (width < 1024) await expect.poll(async () => (await page.locator('main').boundingBox())!.x).toBeLessThan(2)
    else await expect.poll(async () => (await page.locator('main').boundingBox())!.x).toBeGreaterThan(255)
    await expect.poll(() => page.locator('main').evaluate(element => [...element.querySelectorAll('[style]')].every(child => Number(getComputedStyle(child).opacity) >= 0.99))).toBe(true)
    await page.screenshot({ path: `../artifacts/onboarding-a2/doctor-${width}.png`, fullPage: true })
  }
  // Approximate 200% reflow on a 1440px display; this is not native browser zoom.
  const zoomContext = await browser.newContext({ baseURL: page.url(), viewport: { width: 720, height: 500 }, deviceScaleFactor: 2, storageState: await page.context().storageState() })
  const zoomPage = await zoomContext.newPage()
  await zoomPage.goto('/dashboard/doctor')
  await expect(zoomPage.getByRole('link', { name: 'Добавить пациента', exact: true }).first()).toBeVisible()
  await noOverflow(zoomPage)
  await expect(zoomPage.getByText('Задач пока нет. Новые приглашения, запросы мнения и архивы на проверке появятся здесь.')).toBeVisible()
  await expect.poll(() => zoomPage.locator('main').evaluate(element => [...element.querySelectorAll('[style]')].every(child => Number(getComputedStyle(child).opacity) >= 0.99))).toBe(true)
  await zoomPage.screenshot({ path: '../artifacts/onboarding-a2/doctor-zoom200.png', fullPage: true })
  await tabTo(zoomPage, 'Добавить пациента')
  await zoomPage.keyboard.press('Enter')
  await expect(zoomPage.getByRole('dialog', { name: 'Новый пациент' })).toBeVisible()
  await expect(zoomPage.getByLabel('Фамилия *', { exact: true })).toBeFocused()
  await zoomPage.getByLabel('Фамилия *', { exact: true }).fill('Синтетический')
  await zoomPage.keyboard.press('Tab')
  await expect(zoomPage.getByLabel('Имя *', { exact: true })).toBeFocused()
  await zoomPage.keyboard.type('Пациент A2')
  await zoomPage.getByRole('button', { name: 'Создать', exact: true }).focus()
  await zoomPage.keyboard.press('Tab')
  await expect(zoomPage.getByRole('button', { name: 'Закрыть создание пациента' })).toBeFocused()
  await zoomPage.keyboard.press('Shift+Tab')
  await expect(zoomPage.getByRole('button', { name: 'Создать', exact: true })).toBeFocused()
  await zoomPage.keyboard.press('Enter')
  await expect(zoomPage.getByRole('dialog')).toHaveCount(0)
  await expect(zoomPage.getByText('Синтетический Пациент A2', { exact: true })).toBeVisible()
  await zoomContext.close()
  await page.goto('/dashboard/doctor')
  await expect(page.getByRole('link', { name: 'Новый клинический случай' })).toBeVisible()
  await expect(page.getByRole('link', { name: /Синтетический Пациент A2 Записей: 0/ })).toBeVisible()
})
