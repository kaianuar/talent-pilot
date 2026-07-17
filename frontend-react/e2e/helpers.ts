import type { Page } from '@playwright/test';

/**
 * Wait for the app to be fully loaded
 */
export async function waitForAppLoad(page: Page) {
  await page.waitForSelector('text=TalentPilot', { timeout: 10000 });
}

/**
 * Upload a CV PDF file
 */
export async function uploadCV(page: Page, filePath: string) {
  // Find the hidden file input
  const fileInput = page.locator('input[type="file"][accept=".pdf"]');
  await fileInput.setInputFiles(filePath);
  
  // Wait for upload to complete - look for success message
  await page.waitForSelector('text=successfully parsed', { timeout: 30000 });
}

/**
 * Wait for job matches to appear in sidebar
 */
export async function waitForMatches(page: Page) {
  await page.waitForSelector('text=Job Matches', { timeout: 10000 });
  // Wait for match cards to load
  await page.waitForSelector('text=Start Screening', { timeout: 15000 });
}

/**
 * Click the first Start Screening button
 */
export async function startScreening(page: Page) {
  const startButton = page.locator('button:has-text("Start Screening")').first();
  await startButton.click();
  // Wait for screening to start (gRPC call takes time)
  await page.waitForSelector('text=Question', { timeout: 30000 });
}

/**
 * Type and submit an answer in the screening flow
 */
export async function submitAnswer(page: Page, answerText: string) {
  const input = page.locator('textarea[placeholder="Type your answer..."]');
  await input.fill(answerText);
  
  const sendButton = page.locator('button').filter({ has: page.locator('[data-testid="SendIcon"]') });
  await sendButton.click();
}

/**
 * Send a chat message
 */
export async function sendChatMessage(page: Page, message: string) {
  const input = page.locator('input[placeholder="Type your message..."]');
  await input.fill(message);
  
  const sendButton = page.locator('button').filter({ has: page.locator('[data-testid="SendIcon"]') });
  await sendButton.click();
  
  // Wait for response
  await page.waitForTimeout(2000);
}
