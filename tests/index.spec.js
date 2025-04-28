import { test, expect } from '@playwright/test';

test('test', async ({ page }) => {
  await page.goto('http://localhost:8000/tests/index.html');
  await page.waitForSelector('body.done');
  const text = await page.textContent('body.done');
  expect(text).toBe('OK');
});
