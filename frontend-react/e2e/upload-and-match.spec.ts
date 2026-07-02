import { test, expect } from '@playwright/test';
import { waitForAppLoad, uploadCV, waitForMatches } from './helpers';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const sampleCV = path.join(__dirname, 'fixtures', 'sample_cv.pdf');

test.describe('CV Upload and Job Matching', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForAppLoad(page);
  });

  test('shows welcome message on initial load', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'TalentPilot' })).toBeVisible();
    await expect(page.getByText(/Upload your CV/).first()).toBeVisible();
  });

  test('shows job matches placeholder before upload', async ({ page }) => {
    await expect(page.getByText('Upload your CV to see job matches!')).toBeVisible();
  });

  test('shows profile placeholder before upload', async ({ page }) => {
    await expect(page.getByText('Upload your CV to see your profile details!')).toBeVisible();
  });

  test('uploads CV and shows parsed result', async ({ page }) => {
    await uploadCV(page, sampleCV);
    await expect(page.getByText(/successfully parsed/)).toBeVisible();
  });

  test('shows job matches after CV upload', async ({ page }) => {
    await uploadCV(page, sampleCV);
    await waitForMatches(page);
    await expect(page.getByRole('button', { name: 'Start Screening' }).first()).toBeVisible();
  });

  test('shows profile after CV upload', async ({ page }) => {
    await uploadCV(page, sampleCV);
    await page.waitForSelector('text=years experience', { timeout: 10000 });
    await expect(page.getByText(/years experience/).first()).toBeVisible();
  });
});
