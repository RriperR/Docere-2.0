import { expect, test, type APIRequestContext } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const password = 'DemoPass123'
const fixture = (name: string) => readFileSync(resolve(process.cwd(), '../tests/fixtures/import_ai', name))
async function accessToken(request: APIRequestContext, email: string) {
  const response = await request.post('/api/auth/login', { data: { email, password } })
  expect(response.ok(), await response.text()).toBeTruthy()
  return (await response.json()).access_token as string
}

test('doctor checks AI sources, preserves corrections, and imports reviewed records', async ({ page, request }, testInfo) => {
  test.setTimeout(180_000)
  await page.goto('/auth/login')
  await page.getByLabel('Email').fill('dr.sokolov@docere.demo')
  await page.getByLabel('Пароль', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).toHaveURL(/\/dashboard\/doctor$/)
  await page.goto('/upload')
  await page.locator('input[type=file]').setInputFiles([
    { name: 'synthetic-report.pdf', mimeType: 'application/pdf', buffer: fixture('synthetic-report.pdf') },
    { name: 'synthetic-scan.png', mimeType: 'image/png', buffer: fixture('synthetic-scan.png') },
  ])
  await expect(page.getByRole('checkbox', { name: 'Проанализировать с AI' })).not.toBeChecked()
  await page.getByRole('checkbox', { name: 'Проанализировать с AI' }).check()
  await page.getByRole('button', { name: 'Загрузить', exact: true }).click()
  await expect(page).toHaveURL(/\/upload\/status\//)
  const jobId = page.url().split('/').at(-1)!
  await page.locator(`a[href="/upload/review/${jobId}"]`).getByRole('button', { name: 'Проверить импорт' }).click()
  await expect(page).toHaveURL(/\/upload\/review\//)
  await expect(page.getByRole('button', { name: 'Заполнить пустые поля' })).toHaveCount(2)
  await page.getByRole('button', { name: 'Заполнить пустые поля' }).first().click()
  await page.getByRole('button', { name: 'Заполнить пустые поля' }).last().click()
  await page.getByLabel('Клиническое описание').first().fill('Описание исправлено и проверено врачом')
  await page.getByRole('checkbox', { name: 'Я проверил, что документ относится к выбранному пациенту' }).first().check()
  await page.getByRole('checkbox', { name: 'Я проверил, что документ относится к выбранному пациенту' }).last().check()
  const source = page.getByRole('button', { name: /Стр\. 1: «Synthetic examination completed\./ }).first()
  await source.click()
  await expect(page.getByTitle('Просмотр PDF')).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('ai-review-1440.png'), fullPage: true })
  const ownerHeaders = { Authorization: `Bearer ${await accessToken(request, 'dr.sokolov@docere.demo')}` }
  await expect.poll(async () => {
    const job = await (await request.get(`/api/archives/imports/${jobId}`, { headers: ownerHeaders })).json()
    return job.review_decisions[0]?.record_groups[0]?.clinical_summary
  }).toBe('Описание исправлено и проверено врачом')
  await page.reload()
  await expect(page.getByLabel('Клиническое описание').first()).toHaveValue('Описание исправлено и проверено врачом')
  await page.getByRole('checkbox', { name: 'synthetic-report.pdf', exact: true }).check()
  await page.getByRole('button', { name: 'Проанализировать выбранные' }).click()
  await expect(page.getByText(/обработано 1 из 1/)).toBeVisible()
  await expect(page.getByLabel('Клиническое описание').first()).toHaveValue('Описание исправлено и проверено врачом')
  const job = await (await request.get(`/api/archives/imports/${jobId}`, { headers: ownerHeaders })).json()
  const runId = job.report_json.latest_ai_run_id
  const outsiderHeaders = { Authorization: `Bearer ${await accessToken(request, 'dr.kim@docere.demo')}` }
  const fileId = job.report_json.patients[0].record_groups[0].files[0].id
  expect((await request.get(`/api/archives/imports/${jobId}/files/${fileId}`, { headers: outsiderHeaders })).status()).toBe(404)
  expect((await request.get(`/api/archives/imports/${jobId}/ai-runs/${runId}`, { headers: outsiderHeaders })).status()).toBe(404)
  await page.getByRole('button', { name: /Стр\. 1: «Synthetic examination completed\./ }).first().click()
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    await expect.poll(() => page.evaluate(() => getComputedStyle(document.getElementById('main-content')!.parentElement!).paddingLeft)).toBe(width >= 1024 ? '256px' : '0px')
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
    if (width === 390) {
      await expect(page.getByTitle('Просмотр PDF')).toBeVisible()
      await page.getByRole('button', { name: 'Поля', exact: true }).click()
      await expect(page.getByLabel('Клиническое описание').first()).toBeVisible()
    }
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: testInfo.outputPath(`ai-review-${width}.png`), fullPage: true })
  }
  await page.getByRole('button', { name: 'synthetic-scan.png', exact: true }).click()
  await expect(page.getByAltText('Вложение медицинской записи')).toBeVisible()
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: testInfo.outputPath('ai-review-image-1440.png'), fullPage: true })
  await page.getByRole('button', { name: 'На весь экран' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'На весь экран' })).toBeFocused()
  await page.getByRole('button', { name: 'Закрыть просмотр' }).click()
  await page.evaluate(() => { document.documentElement.style.zoom = '2' })
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
  await page.evaluate(() => { document.documentElement.style.zoom = '' })
  page.on('dialog', dialog => void dialog.accept())
  await page.getByRole('button', { name: 'Подтвердить импорт' }).click()
  await expect(page).toHaveURL(/\/upload\/status\//)
  const final = await (await request.get(`/api/archives/imports/${jobId}`, { headers: ownerHeaders })).json()
  expect(final.status).toBe('completed')
  const recordIds = final.report_json.resolved_patients[0].record_ids
  expect(recordIds).toHaveLength(2)
  const firstRecord = await (await request.get(`/api/records/${recordIds[0]}`, { headers: ownerHeaders })).json()
  expect(firstRecord.clinical_summary).toBe('Описание исправлено и проверено врачом')
  expect(firstRecord.status).toBe('unconfirmed')
  expect(firstRecord.attachments).toHaveLength(1)
  expect(firstRecord.payload_json.import_provenance.ai_assistance.length).toBeGreaterThan(0)
  const repeated = await request.post(`/api/archives/imports/${jobId}/resolve`, { headers: ownerHeaders, data: { decisions: job.review_decisions, version: job.version } })
  expect((await repeated.json()).report_json.resolved_patients[0].record_ids).toEqual(recordIds)
  await page.goto(`/patients/${firstRecord.patient_passport_id}?record=${recordIds[0]}`)
  await expect(page.getByLabel('Просмотр документа')).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('ai-imported-history.png'), fullPage: true })
  await page.getByRole('button', { name: 'Выйти', exact: true }).first().click()
  await expect(page).toHaveURL(/auth\/login/)
  await page.getByLabel('Email').fill('dr.kim@docere.demo')
  await page.getByLabel('Пароль', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).toHaveURL(/dashboard\/doctor$/)
  await page.goto(`/upload/review/${jobId}`)
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.getByText('Synthetic Patient', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Просмотр документа')).toHaveCount(0)
})
