import { test, expect } from '@playwright/test'

const TEST_EMAIL = `e2e-${Date.now()}@test.com`
const TEST_PASSWORD = 'TestPassword123!'

test.describe('Auth flow', () => {
  test('register a new user', async ({ page }) => {
    await page.goto('/register')

    await page.getByLabel('Email').fill(TEST_EMAIL)
    await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD)
    await page.getByLabel('Confirm Password').fill(TEST_PASSWORD)
    await page.getByRole('button', { name: 'Register' }).click()

    // Should redirect to login page on success
    await expect(page).toHaveURL(/\/login/)
  })

  test('login with credentials', async ({ page }) => {
    await page.goto('/login')

    await page.getByLabel('Email').fill(TEST_EMAIL)
    await page.getByLabel('Password').fill(TEST_PASSWORD)
    await page.getByRole('button', { name: 'Login' }).click()

    // Should redirect to dashboard after login
    await expect(page).toHaveURL(/\/dashboard/)
  })

  test('redirect to dashboard after login', async ({ page }) => {
    await page.goto('/login')

    await page.getByLabel('Email').fill(TEST_EMAIL)
    await page.getByLabel('Password').fill(TEST_PASSWORD)
    await page.getByRole('button', { name: 'Login' }).click()

    await expect(page).toHaveURL(/\/dashboard/)
    // Dashboard heading should be visible
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  })

  test('dashboard shows content when authenticated', async ({ page }) => {
    // Login first
    await page.goto('/login')
    await page.getByLabel('Email').fill(TEST_EMAIL)
    await page.getByLabel('Password').fill(TEST_PASSWORD)
    await page.getByRole('button', { name: 'Login' }).click()
    await expect(page).toHaveURL(/\/dashboard/)

    // Dashboard should show portfolio content (either portfolio data or empty state)
    await expect(
      page.getByTestId('total-value').or(page.getByTestId('empty-portfolio'))
    ).toBeVisible()
  })

  test('redirect to login when not authenticated', async ({ page }) => {
    // Clear any stored auth tokens
    await page.goto('/')
    await page.evaluate(() => localStorage.removeItem('mm_auth_tokens'))

    // Navigate to protected route
    await page.goto('/dashboard')

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/)
  })
})
