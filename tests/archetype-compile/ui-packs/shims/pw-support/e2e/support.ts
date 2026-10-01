// HARNESS STUB (app-level e2e helpers): what testing/playwright.md's security rows call — a persona's seeded
// credentials, signing in through the UI, and creating data through the product API as that persona.
import { request, type Page } from "@playwright/test";

export const SESSION_COOKIE = "session";
export type Persona = { email: string; password: string };

// Seeded test personas: credentials come from the environment the seed step exported, never from a spec.
export function persona(name: "buyer" | "admin"): Persona {
  const key = name.toUpperCase();
  const email = process.env[`E2E_${key}_EMAIL`], password = process.env[`E2E_${key}_PASSWORD`];
  if (!email || !password) throw new Error(`E2E_${key}_EMAIL / E2E_${key}_PASSWORD not set`);
  return { email, password };
}

export async function signIn(page: Page, who: Persona) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(who.email);
  await page.getByLabel("Password").fill(who.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard");
}

export async function createNoteViaApi(who: Persona, text: string) {
  const api = await request.newContext({ baseURL: process.env.APP_BASE_URL });
  try {
    const login = await api.post("/api/v1/auth/login", { data: who });
    if (!login.ok()) throw new Error(`login failed: ${login.status()}`);
    const res = await api.post("/api/v1/notes", { data: { text } });
    if (res.status() !== 201) throw new Error(`create note failed: ${res.status()}`);
  } finally {
    await api.dispose();
  }
}
