// HARNESS STUB (app-level): a tiny stand-in for "the deployed app" the Playwright samples in testing/playwright.md
// run against (APP_BASE_URL). Node's http module only. Session in an httpOnly cookie, the one envelope, no inline
// scripts (pages load /app.js), text rendered with textContent.
//   node server.mjs <port>
import { createServer } from "node:http";
import { randomUUID } from "node:crypto";

const port = Number(process.argv[2] ?? 4173);
const sessions = new Set();
const notes = [];
const users = new Map([["alice@example.com", "password123"]]);
if (process.env.E2E_ADMIN_EMAIL) users.set(process.env.E2E_ADMIN_EMAIL, process.env.E2E_ADMIN_PASSWORD ?? "");
const persona = (email) => /^([a-z]+)@example\.com$/.exec(email)?.[1];

const page = (title, body) => `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>${title}</title><script src="/app.js" defer></script></head>
<body><main>${body}</main></body></html>`;

const PAGES = {
  "/login": page("Sign in | App", `<h1>Sign in</h1>
    <form id="login" novalidate>
      <label for="email">Email</label> <input id="email" name="email" type="email" autocomplete="username">
      <label for="password">Password</label> <input id="password" name="password" type="password" autocomplete="current-password">
      <button type="submit">Sign in</button>
    </form>
    <div id="login-error"></div>`),
  "/dashboard": page("Dashboard | App", `<h1>Dashboard</h1>
    <p>Success</p>
    <label for="who">Signed in as</label> <input id="who" value="alice@example.com" readonly>
    <ul data-testid="item-list"><li>One</li><li>Two</li><li>Three</li></ul>
    <button type="button">Refresh</button>`),
  "/orders/new": page("New order | App", `<h1>New order</h1>
    <form>
      <label for="sku">SKU</label> <input id="sku" name="sku" required>
      <label for="qty">Quantity</label> <input id="qty" name="qty" type="number" min="1" value="1">
      <button type="submit">Place order</button>
    </form>`),
  "/notes": page("Notes | App", `<h1>Notes</h1><ul id="notes"></ul>`),
};

const APP_JS = `
const form = document.getElementById("login");
if (form) form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const res = await fetch("/api/v1/auth/login", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: form.email.value, password: form.password.value }) });
  if (res.ok) { location.assign("/dashboard"); return; }
  const box = document.getElementById("login-error");
  box.setAttribute("role", "alert");
  box.textContent = (await res.json()).error.message;
});
const list = document.getElementById("notes");
if (list) fetch("/api/v1/notes").then((r) => r.json()).then((body) => {
  for (const n of body.data) { const li = document.createElement("li"); li.textContent = n.text; list.append(li); }
});`;

function send(res, status, body, headers = {}) {
  const rid = randomUUID();
  res.writeHead(status, { "X-Request-Id": rid, ...headers });
  res.end(typeof body === "string" ? body : JSON.stringify(body));
}
const json = (res, status, data, extra = {}) =>
  send(res, status, { data, meta: { request_id: "pw-" + Date.now() } }, { "Content-Type": "application/json", ...extra });
const error = (res, status, code, message) =>
  send(res, status, { error: { code, message, request_id: "pw-" + Date.now(), retryable: false } }, { "Content-Type": "application/json" });
const cookie = (req, name) => (req.headers.cookie ?? "").split("; ").find((c) => c.startsWith(name + "="))?.slice(name.length + 1);
const readJson = (req) => new Promise((resolve) => {
  let raw = "";
  req.on("data", (c) => (raw += c));
  req.on("end", () => { try { resolve(JSON.parse(raw || "{}")); } catch { resolve({}); } });
});

createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", `http://localhost:${port}`);
  if (req.method === "GET" && PAGES[url.pathname]) return send(res, 200, PAGES[url.pathname], { "Content-Type": "text/html; charset=utf-8" });
  if (req.method === "GET" && url.pathname === "/app.js") return send(res, 200, APP_JS, { "Content-Type": "text/javascript" });
  if (req.method === "GET" && url.pathname === "/healthz") return send(res, 200, { status: "ok" }, { "Content-Type": "application/json" });
  if (req.method === "POST" && url.pathname === "/api/v1/auth/login") {
    const { email = "", password = "" } = await readJson(req);
    const ok = users.get(email) === password || (persona(email) && password === `${persona(email)}-pass-1`);
    if (!ok) return error(res, 401, "UNAUTHENTICATED", "Invalid credentials");
    const sid = randomUUID();
    sessions.add(sid);
    return json(res, 200, { email }, { "Set-Cookie": `session=${sid}; HttpOnly; Secure; SameSite=Lax; Path=/` });
  }
  if (url.pathname === "/api/v1/notes") {
    if (req.method === "GET") return json(res, 200, notes);
    if (req.method === "POST") {
      if (!sessions.has(cookie(req, "session"))) return error(res, 401, "UNAUTHENTICATED", "Sign in first.");
      const { text = "" } = await readJson(req);
      const note = { id: String(notes.length + 1), text };
      notes.push(note);
      return json(res, 201, note);
    }
  }
  if (req.method === "GET" && url.pathname === "/api/v1/users") return json(res, 200, [], {});
  return error(res, 404, "NOT_FOUND", "Not found.");
}).listen(port, "localhost"); // loopback only; APP_BASE_URL is http://localhost:<port>
