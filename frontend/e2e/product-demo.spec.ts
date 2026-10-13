import { readFileSync } from 'node:fs'
import { expect, test, type Page } from '@playwright/test'

type DemoState = {
  accounts: { key: string; email: string; password: string }[]
  patient: { id: string }
  cases: { active: string; complete: string; draft: string }
  imports: { completed: string; review: string }
  texts: { reply: string; summary: string }
  records: string[]
}
const statePath = process.env.PRODUCT_DEMO_STATE
const state: DemoState | null = statePath ? JSON.parse(readFileSync(statePath, 'utf8')) as DemoState : null

async function login(page: Page, key: string) {
  const account = state!.accounts.find(item => item.key === key)!
  await page.goto('/auth/login')
  await page.getByLabel('Email', { exact: true }).fill(account.email)
  await page.getByLabel('Пароль', { exact: true }).fill(account.password)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).toHaveURL(/\/dashboard\/doctor$/)
}

test('synthetic product demo: source documents, chronology, colleague response and saved conclusion', async ({ page, browser, request }) => {
  test.skip(!state, 'Run scripts/product_demo_setup.mjs and pass PRODUCT_DEMO_STATE (new synthetic accounts only)')
  test.setTimeout(180_000)
  page.setDefaultTimeout(15_000)
  await login(page, 'coordinator')
  const access = await page.evaluate(() => JSON.parse(localStorage.getItem('authTokens')!).access_token as string)
  const headers = { Authorization: `Bearer ${access}` }
  const imported = await request.get(`/api/archives/imports/${state!.imports.completed}`, { headers })
  expect(imported.ok()).toBeTruthy()
  const importData = await imported.json()
  expect(importData.status).toBe('completed')
  expect(importData.report_json.ai_requested).toBe(false)
  expect(importData.report_json.resolved_patients.flatMap((item: { record_ids: string[] }) => item.record_ids)).toHaveLength(3)
  const pending = await request.get(`/api/archives/imports/${state!.imports.review}`, { headers })
  expect((await pending.json()).status).toBe('needs_review')

  await page.goto(`/patients/${state!.patient.id}`)
  await expect(page.getByText('Демонстрационная Анна Сергеевна', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Консультация терапевта · сердцебиение', { exact: true })).toBeVisible()
  await expect(page.getByText('ЭКГ · исходное исследование', { exact: true })).toBeVisible()
  await expect(page.getByText('Мониторирование · дневник и заключение', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: /Мониторирование · дневник и заключение/ }).click()
  await page.getByRole('button', { name: /2026-09-25-monitoring\.png/ }).click()
  await expect(page.getByAltText('Вложение медицинской записи')).toBeVisible()

  const context = await browser.newContext({ baseURL: test.info().project.use.baseURL })
  try {
    const colleague = await context.newPage()
    colleague.setDefaultTimeout(15_000)
    await login(colleague, 'colleague')
    await colleague.goto(`/cases/${state!.cases.active}`)
    await expect(colleague.getByRole('heading', { name: 'Нужен ответ · дневник и мониторирование' })).toBeVisible()
    await colleague.getByRole('button', { name: 'Ответить на запрос', exact: true }).click()
    await colleague.getByLabel('Сообщение', { exact: true }).fill(state!.texts.reply)
    await colleague.getByRole('button', { name: 'Отправить сообщение', exact: true }).click()
    await expect(colleague.getByText(state!.texts.reply, { exact: true })).toBeVisible()
    await expect(colleague.getByRole('button', { name: 'Ответить на запрос', exact: true })).toHaveCount(0)

    await page.goto(`/cases/${state!.cases.active}`)
    await expect(page.getByText(state!.texts.reply, { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Итог', exact: true }).click()
    await page.getByRole('button', { name: 'Составить новую версию итога' }).click()
    await page.getByLabel('Краткое резюме', { exact: true }).fill(state!.texts.summary)
    await page.getByLabel('Выводы', { exact: true }).fill('Учебный разбор: ответ коллеги получен, ограничение данных явно сохранено.')
    await page.getByLabel('Дальнейшие действия', { exact: true }).fill('Учебное действие: запросить уточнение времени у автора документа.')
    await page.getByRole('button', { name: 'Сохранить версию итога' }).click()
    await expect(page.getByText(state!.texts.summary, { exact: true })).toBeVisible()
    const opinions = await request.get(`/api/cases/${state!.cases.active}/opinions`, { headers })
    expect((await opinions.json()).items[0].status).toBe('answered')
    const conclusions = await request.get(`/api/cases/${state!.cases.active}/conclusions`, { headers })
    expect((await conclusions.json()).items[0].summary).toBe(state!.texts.summary)

    await page.goto(`/cases/${state!.cases.complete}?tab=conclusion`)
    await expect(page.getByText(state!.texts.summary, { exact: true })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Открыть историю пациента', exact: true })).toBeVisible()
  } finally { await context.close() }
})
