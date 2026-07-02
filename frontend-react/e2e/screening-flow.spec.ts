import { test, expect } from '@playwright/test';
import { waitForAppLoad, uploadCV, waitForMatches, startScreening, submitAnswer } from './helpers';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const sampleCV = path.join(__dirname, 'fixtures', 'sample_cv.pdf');

test.describe('Screening Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForAppLoad(page);
    await uploadCV(page, sampleCV);
    await waitForMatches(page);
  });

  test('starts screening when clicking Start Screening', async ({ page }) => {
    await startScreening(page);
    await expect(page.getByText(/Question \d+ of \d+/)).toBeVisible();
  });

  test('shows question text after starting', async ({ page }) => {
    await startScreening(page);
    const questionArea = page.locator('p.MuiTypography-body1');
    await expect(questionArea).toBeVisible();
    const text = await questionArea.textContent();
    expect(text?.length).toBeGreaterThan(10);
  });

  test('shows answer input and submit button', async ({ page }) => {
    await startScreening(page);
    await expect(page.locator('textarea[placeholder="Type your answer..."]')).toBeVisible();
  });

  test('submits answer and shows assessment feedback', async ({ page }) => {
    await startScreening(page);
    await submitAnswer(page,
      'I have 5 years of experience with Python and React. ' +
      'I led a team of 4 engineers to build a microservices platform ' +
      'that handles 10K requests per second with 99.9% uptime.'
    );
    await page.waitForSelector('[role="alert"]', { timeout: 10000 });
  });

  test('shows progress indicator', async ({ page }) => {
    await startScreening(page);
    await expect(page.getByRole('progressbar').first()).toBeVisible();
  });

  test('shows cancel button', async ({ page }) => {
    await startScreening(page);
    await expect(page.getByText('Cancel Screening')).toBeVisible();
  });

  test('cancels screening and returns to chat', async ({ page }) => {
    await startScreening(page);
    await page.getByText('Cancel Screening').click();
    await expect(page.locator('input[placeholder="Type your message..."]')).toBeVisible({ timeout: 10000 });
  });
});
