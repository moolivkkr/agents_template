// HARNESS STUB (app-level e2e helpers): what testing/playwright.md's security rows call — a persona's seeded
// credentials, signing in through the UI, and creating data through the product API as that persona.
import { request, type Page } from "@playwright/test";

export const SESSION_COOKIE = "session";
export type Persona = { email: string; password: string };

// Seeded test personas (the stub server accepts <name>@example.com / <name>-pass-1).
export const persona = (name: "buyer" | "admin"): Persona => ({ email: `${name}@example.com`, password: `${name}-pass-1` });

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
