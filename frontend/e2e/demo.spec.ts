import { expect, type Page, test } from '@playwright/test'

const doctorEmail = 'dr.sokolov@docere.demo'
const demoPassword = 'DemoPass123'

const login = async (page: Page) => {
  await page.goto('/auth/login')
  await page.getByLabel('Email').fill(doctorEmail)
  await page.getByLabel('Пароль').fill(demoPassword)
  await page.getByRole('button', { name: 'Войти' }).click()
  await expect(page).toHaveURL(/\/dashboard\/doctor$/)
}

test('doctor can authenticate with the keyboard-accessible form', async ({ page }) => {
  await page.goto('/auth/login')
  await page.getByLabel('Email').fill(doctorEmail)
  await page.getByLabel('Email').press('Tab')
  await expect(page.getByLabel('Пароль')).toBeFocused()
  await page.getByLabel('Пароль').fill(demoPassword)
  await page.getByLabel('Пароль').press('Enter')
  await expect(page.getByRole('heading', { name: 'Рабочее место врача' })).toBeVisible()
})

test('sharing workspace remains usable at tablet width', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 })
  await login(page)
  await page.goto('/share-requests')
  await expect(page.getByRole('heading', { name: 'Sharing записей' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Входящие/ })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Исходящие' })).toBeVisible()
})

test('doctor completes archive upload, review and result navigation', async ({ page }) => {
  await login(page)
  await page.goto('/upload')
  await page.locator('input[type="file"]').setInputFiles('/fixtures/docere-demo-archive.zip')
  await page.getByRole('button', { name: 'Загрузить' }).click()
  await expect(page.getByRole('button', { name: 'Проверить импорт' })).toBeVisible({ timeout: 90_000 })
  await page.getByRole('button', { name: 'Проверить импорт' }).click()

  for (const button of await page.getByRole('button', { name: 'Применить найденные даты' }).all()) {
    await button.click()
  }
  for (const button of await page.getByRole('button', { name: 'Импортировать всё равно' }).all()) {
    await button.click()
  }

  await expect(page.getByText('Требуют решения: 0')).toBeVisible()
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: 'Подтвердить импорт' }).click()

  await expect(page.getByText('Результат импорта')).toBeVisible({ timeout: 30_000 })
  const resultLink = page.getByRole('link', { name: 'Открыть медицинскую историю' }).first()
  await expect(resultLink).toBeVisible()
  await resultLink.click()
  await expect(page).toHaveURL(/\/patients\/.+#record-/)
})
