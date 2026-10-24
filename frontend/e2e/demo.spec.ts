import { expect, type Page, test } from '@playwright/test'

const doctorEmail = 'dr.sokolov@docere.demo'
const demoPassword = 'DemoPass123'

const login = async (page: Page) => {
  await page.goto('/auth/login')
  await page.getByLabel('Email').fill(doctorEmail)
  await page.getByLabel('Пароль', { exact: true }).fill(demoPassword)
  await page.getByRole('button', { name: 'Войти' }).click()
  await expect(page).toHaveURL(/\/dashboard\/doctor$/)
}

test('doctor can authenticate with the keyboard-accessible form', async ({ page }) => {
  await page.goto('/auth/login')
  // Проверяем готовую CSS-сборку: общие поля не должны подавлять отступы формы.
  const email = page.getByLabel('Email')
  await expect(page.getByRole('button', { name: 'Войти' })).toHaveCSS('background-color', 'rgb(26, 111, 179)')
  const emailBox = await email.boundingBox()
  const passwordLabelBox = await page.locator('label[for="password"]').boundingBox()
  expect(emailBox).not.toBeNull()
  expect(passwordLabelBox).not.toBeNull()
  expect(passwordLabelBox!.y - emailBox!.y - emailBox!.height).toBeGreaterThanOrEqual(12)
  await page.getByLabel('Email').fill(doctorEmail)
  await page.getByLabel('Email').press('Tab')
  await expect(page.getByLabel('Пароль', { exact: true })).toBeFocused()
  await page.getByLabel('Пароль', { exact: true }).fill(demoPassword)
  await page.getByLabel('Пароль', { exact: true }).press('Enter')
  await expect(page).toHaveURL(/\/dashboard\/doctor$/)
  await expect(page.getByRole('heading', { name: 'Рабочий стол', exact: true })).toBeVisible()
})

test('sharing workspace remains usable at tablet width', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 })
  await login(page)
  await page.goto('/share-requests')
  await expect(page.getByRole('heading', { name: 'Доступ к записям' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Входящие/ })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Исходящие' })).toBeVisible()
})

test('doctor completes archive upload, review and result navigation', async ({ page }) => {
  await login(page)
  await page.goto('/upload')
  await page.locator('input[type="file"]').setInputFiles('/fixtures/docere-demo-archive.zip')
  await page.getByRole('button', { name: 'Загрузить' }).click()
  await expect(page).toHaveURL(/\/upload\/status\/[\w-]+$/)
  await expect(page.getByRole('button', { name: 'Проверить документы' })).toBeVisible({ timeout: 90_000 })
  await page.getByRole('button', { name: 'Проверить документы' }).click()

  const documents = page.getByRole('navigation', { name: 'Документы импорта' })
  await expect(documents.getByRole('button').first()).toBeVisible()
  const count = await documents.getByRole('button').count()
  expect(count).toBeGreaterThan(0)
  const runId = Date.now()
  for (let index = 0; index < count; index += 1) {
    await documents.getByRole('button').nth(index).click()
    await expect(page.getByRole('textbox', { name: 'Название', exact: true })).toHaveCount(1)
    await page.getByRole('textbox', { name: 'Название', exact: true }).fill(`Проверка импорта ${runId} · материал ${index + 1}`)
    const date = page.getByRole('textbox', { name: 'Дата события', exact: true })
    if (!await date.inputValue()) {
      await date.fill('01.05.2026')
      await date.press('Tab')
      await page.keyboard.press('Escape')
    }
    const duplicate = page.getByRole('button', { name: 'Импортировать всё равно', exact: true })
    if (await duplicate.count()) await duplicate.click()
  }
  await expect(page.getByText('Нужны данные: 0 документов', { exact: true })).toBeVisible()
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: `Сохранить ${count} записей в историю`, exact: true }).click()

  await expect(page.getByText('Результат импорта')).toBeVisible({ timeout: 30_000 })
  const resultLink = page.getByRole('link', { name: 'Открыть медицинскую историю' }).first()
  await expect(resultLink).toBeVisible()
  await resultLink.click()
  await expect(page).toHaveURL(/\/patients\/.+#record-/)
})

test('doctor navigates the workspace on a phone without overflow or a stuck menu', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await login(page)
  await expect(page.getByRole('link', { name: 'Новый клинический случай' })).toBeVisible()
  await page.getByRole('button', { name: 'Открыть меню', exact: true }).click()
  await page.getByRole('navigation', { name: 'Основная навигация' }).getByRole('link', { name: 'Клинические случаи', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Клинические случаи', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Закрыть меню', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Открыть меню', exact: true })).toHaveAttribute('aria-expanded', 'false')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.getByRole('button', { name: /^Входящие:/ }).click()
  await expect(page.getByRole('link', { name: 'Открыть все входящие', exact: true })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: /^Входящие:/ })).toBeFocused()
  await expect(page.getByRole('link', { name: 'Открыть все входящие', exact: true })).toHaveCount(0)
})
