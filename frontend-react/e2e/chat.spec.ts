import { test, expect } from '@playwright/test';
import { waitForAppLoad, sendChatMessage } from './helpers';

test.describe('Chat Interface', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForAppLoad(page);
  });

  test('shows chat input area', async ({ page }) => {
    await expect(page.locator('input[placeholder="Type your message..."]')).toBeVisible();
  });

  test('shows helper chips', async ({ page }) => {
    await expect(page.locator('text=Show my matches')).toBeVisible();
    await expect(page.locator('text=Apply to a job')).toBeVisible();
    await expect(page.locator('text=View my profile')).toBeVisible();
  });

  test('helper chip fills input', async ({ page }) => {
    await page.locator('text=Show my matches').click();
    
    const input = page.locator('input[placeholder="Type your message..."]');
    await expect(input).toHaveValue('Show me my job matches');
  });

  test('sends message and receives response', async ({ page }) => {
    await sendChatMessage(page, 'Hello, what jobs match my profile?');
    
    // Should show user message
    await expect(page.locator('text=Hello, what jobs match my profile?')).toBeVisible();
    
    // Should show assistant response (after API call)
    await page.waitForSelector('[data-testid="SmartToyIcon"]', { timeout: 10000 });
  });

  test('shows attachment button', async ({ page }) => {
    // Should have file upload button
    await expect(page.locator('input[type="file"][accept=".pdf"]')).toBeAttached();
  });
});
