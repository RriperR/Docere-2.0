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
  await page.locator(`a[href="/upload/review/${jobId}"]`).getByRole('button', { name: 'Проверить документы' }).click()
  await expect(page).toHaveURL(/\/upload\/review\//)
  const documents = page.getByRole('navigation', { name: 'Документы импорта' })
  await expect(documents.getByRole('button')).toHaveCount(2)
  for (const filename of ['synthetic-report.pdf', 'synthetic-scan.png']) {
    await documents.getByRole('button').filter({ hasText: filename }).click()
    await expect(page.getByLabel('Клиническое описание', { exact: true })).toHaveCount(1)
    await page.getByRole('button', { name: 'Заполнить пустые поля', exact: true }).click()
    if (filename === 'synthetic-report.pdf') await page.getByLabel('Клиническое описание', { exact: true }).fill('Описание исправлено и проверено врачом')
    await page.getByRole('checkbox', { name: 'Я проверил, что документ относится к выбранному пациенту' }).check()
  }
  await documents.getByRole('button').filter({ hasText: 'synthetic-report.pdf' }).click()
  const summary = page.getByRole('article', { name: 'Предложение: Клиническое описание' })
  await summary.getByText(/Источники предложения/).click()
  await summary.getByRole('button', { name: /Стр\. 1: «Synthetic examination completed\./ }).click()
  await expect(page.getByTitle('Просмотр PDF')).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('ai-review-1440.png'), fullPage: true, animations: 'disabled' })
  const ownerHeaders = { Authorization: `Bearer ${await accessToken(request, 'dr.sokolov@docere.demo')}` }
  await expect.poll(async () => {
    const job = await (await request.get(`/api/archives/imports/${jobId}`, { headers: ownerHeaders })).json()
    const group = job.report_json.patients.flatMap((patient: { record_groups: { group_id: string; files: { filename: string }[] }[] }) => patient.record_groups).find((group: { files: { filename: string }[] }) => group.files.some(file => file.filename === 'synthetic-report.pdf'))
    return job.review_decisions.flatMap((patient: { record_groups: { group_id: string; clinical_summary?: string }[] }) => patient.record_groups).find((decision: { group_id: string }) => decision.group_id === group?.group_id)?.clinical_summary
  }).toBe('Описание исправлено и проверено врачом')
  await page.reload()
  await expect(page.getByLabel('Клиническое описание').first()).toHaveValue('Описание исправлено и проверено врачом')
  const previousRunId = (await (await request.get(`/api/archives/imports/${jobId}`, { headers: ownerHeaders })).json()).report_json.latest_ai_run_id
  await page.getByText('Заполнить поля по документам с AI', { exact: true }).click()
  await page.getByRole('checkbox', { name: 'synthetic-report.pdf', exact: true }).check()
  await page.getByRole('button', { name: 'Проанализировать выбранные' }).click()
  await expect.poll(async () => (await (await request.get(`/api/archives/imports/${jobId}`, { headers: ownerHeaders })).json()).report_json.latest_ai_run_id).not.toBe(previousRunId)
  await expect(page.getByText(/Завершено документов: 1 из 1/)).toBeVisible()
  await expect(page.getByLabel('Клиническое описание').first()).toHaveValue('Описание исправлено и проверено врачом')
  const job = await (await request.get(`/api/archives/imports/${jobId}`, { headers: ownerHeaders })).json()
  const runId = job.report_json.latest_ai_run_id
  const outsiderHeaders = { Authorization: `Bearer ${await accessToken(request, 'dr.kim@docere.demo')}` }
  const fileId = job.report_json.patients[0].record_groups[0].files[0].id
  expect((await request.get(`/api/archives/imports/${jobId}/files/${fileId}`, { headers: outsiderHeaders })).status()).toBe(404)
  expect((await request.get(`/api/archives/imports/${jobId}/ai-runs/${runId}`, { headers: outsiderHeaders })).status()).toBe(404)
  const refreshedSummary = page.getByRole('article', { name: 'Предложение: Клиническое описание' })
  const refreshedSource = refreshedSummary.getByRole('button', { name: /Стр\. 1: «Synthetic examination completed\./ })
  if (!await refreshedSource.isVisible()) await refreshedSummary.getByText(/Источники предложения/).click()
  await refreshedSource.click()
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    await expect.poll(() => page.evaluate(() => getComputedStyle(document.getElementById('main-content')!.parentElement!).paddingLeft)).toBe(width >= 1024 ? '256px' : '0px')
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
    if (width === 390) {
      await expect(page.getByTitle('Просмотр PDF')).toBeVisible()
      await page.getByRole('button', { name: 'Поля записи', exact: true }).click()
      await expect(page.getByLabel('Клиническое описание').first()).toBeVisible()
    }
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: testInfo.outputPath(`ai-review-${width}.png`), fullPage: true })
  }
  await documents.getByRole('button').filter({ hasText: 'synthetic-scan.png' }).click()
  await expect(page.getByAltText('Вложение медицинской записи')).toBeVisible()
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: testInfo.outputPath('ai-review-image-1440.png'), fullPage: true })
  await page.getByRole('button', { name: 'На весь экран' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'На весь экран' })).toBeFocused()
  await page.getByRole('button', { name: 'Закрыть просмотр' }).click()
  // Reflow equivalent of 200% zoom on a 1440px-wide screen; CSS zoom does not update media queries.
  await page.setViewportSize({ width: 720, height: 1000 })
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
  page.on('dialog', dialog => void dialog.accept())
  await page.getByRole('button', { name: 'Сохранить 2 записей в историю' }).click()
  await expect(page).toHaveURL(/\/upload\/status\//)
  const final = await (await request.get(`/api/archives/imports/${jobId}`, { headers: ownerHeaders })).json()
  expect(final.status).toBe('completed')
  const recordIds = final.report_json.resolved_patients[0].record_ids
  expect(recordIds).toHaveLength(2)
  const importedRecords = await Promise.all(recordIds.map(async (id: string) => (await request.get(`/api/records/${id}`, { headers: ownerHeaders })).json()))
  const firstRecord = importedRecords.find(record => record.attachments.some((attachment: { filename: string }) => attachment.filename === 'synthetic-report.pdf'))
  expect(firstRecord).toBeDefined()
  expect(firstRecord.clinical_summary).toBe('Описание исправлено и проверено врачом')
  expect(firstRecord.status).toBe('unconfirmed')
  expect(firstRecord.attachments).toHaveLength(1)
  expect(firstRecord.payload_json.import_provenance.ai_assistance.length).toBeGreaterThan(0)
  const repeated = await request.post(`/api/archives/imports/${jobId}/resolve`, { headers: ownerHeaders, data: { decisions: job.review_decisions, version: job.version } })
  expect((await repeated.json()).report_json.resolved_patients[0].record_ids).toEqual(recordIds)
  await page.goto(`/patients/${firstRecord.patient_passport_id}?record=${firstRecord.id}`)
  await expect(page.getByLabel('Просмотр документа')).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('ai-imported-history.png'), fullPage: true })
  await page.getByRole('button', { name: 'Меню аккаунта', exact: true }).click()
  await page.getByRole('button', { name: 'Выйти', exact: true }).click()
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
