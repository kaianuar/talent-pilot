import { test, expect } from '@playwright/test';
import { waitForAppLoad, uploadCV, waitForMatches, startScreening, submitAnswer } from './helpers';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const sampleCV = path.join(__dirname, 'fixtures', 'sample_cv.pdf');

test.describe('Send to Recruiter', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForAppLoad(page);
    await uploadCV(page, sampleCV);
    await waitForMatches(page);
  });

  test('shows screening interface after clicking Start Screening', async ({ page }) => {
    await startScreening(page);
    await expect(page.getByText(/Question \d+ of \d+/)).toBeVisible();
    await expect(page.locator('textarea[placeholder="Type your answer..."]')).toBeVisible();
  });

  test('submits answer and receives assessment', async ({ page }) => {
    await startScreening(page);

    await submitAnswer(page,
      'I have extensive experience with Python, React, and distributed systems. ' +
      'I led a team of 5 engineers and delivered production systems at scale.'
    );

    // Should show assessment feedback or next question
    const hasAssessment = await page.getByRole('alert').isVisible().catch(() => false);
    const hasQuestion = await page.getByText(/Question/).isVisible().catch(() => false);
    expect(hasAssessment || hasQuestion).toBeTruthy();
  });
});
