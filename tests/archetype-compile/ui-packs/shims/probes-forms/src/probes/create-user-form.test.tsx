// HARNESS PROBE: renders ui/form-patterns.md's CreateUserForm (shadcn Field + react-hook-form Controller) and drives
// it like a user: client validation errors on their fields, a Radix Select choice, the POST body and Idempotency-Key,
// a 400 VALIDATION_FAILED mapped onto its field, and reset after success.
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { CreateUserForm } from "@/components/create-user-form";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const created = (body: Record<string, string>) =>
  HttpResponse.json({ data: { id: "u9", ...body, avatar_url: null, active: true, created_at: "", updated_at: "" }, meta: { request_id: "r" } }, { status: 201 });

describe("form-patterns.md — CreateUserForm", () => {
  it("shows each client-side error on its own field, labelled and announced", async () => {
    const user = userEvent.setup();
    render(<CreateUserForm />);
    await user.click(screen.getByRole("button", { name: /create user/i }));
    expect(await screen.findByText("Name must be at least 2 characters")).toHaveAttribute("role", "alert");
    expect(screen.getByText("Enter a valid email address")).toBeVisible();
    expect(screen.getByText("Select a role")).toBeVisible();
    expect(screen.getByLabelText("Name")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
  });

  it("posts the payload with an Idempotency-Key, maps a 400 onto the field, and resets after success", async () => {
    const posts: { body: Record<string, string>; key: string | null }[] = [];
    server.use(http.post("/api/v1/users", async ({ request }) => {
      const body = (await request.json()) as Record<string, string>;
      posts.push({ body, key: request.headers.get("idempotency-key") });
      if (posts.length === 1) {
        return HttpResponse.json({ error: { code: "VALIDATION_FAILED", message: "Some fields are invalid.", request_id: "r", retryable: false,
          details: [{ field: "email", code: "already_taken", message: "That email is already registered." }] } }, { status: 400 });
      }
      return created(body);
    }));
    // Radix leaves body pointer-events:none for a tick after the listbox closes; jsdom never repaints, so skip that check
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    render(<CreateUserForm />);
    await user.type(screen.getByLabelText("Name"), "Jane Doe");
    await user.type(screen.getByLabelText("Email"), "jane@company.com");
    await user.click(screen.getByLabelText("Role"));
    await user.click(await screen.findByRole("option", { name: "Member" }));
    await user.click(screen.getByRole("button", { name: /create user/i }));

    expect(await screen.findByText("That email is already registered.")).toHaveAttribute("role", "alert");
    expect(posts[0]?.body).toEqual({ name: "Jane Doe", email: "jane@company.com", role: "member" });

    await user.clear(screen.getByLabelText("Email"));
    await user.type(screen.getByLabelText("Email"), "jane.doe@company.com");
    await user.click(screen.getByRole("button", { name: /create user/i }));
    await waitFor(() => expect(posts).toHaveLength(2));
    expect(posts[1]?.key).toBe(posts[0]?.key); // the same user action, retried after the 400
    await waitFor(() => expect(screen.getByLabelText("Name")).toHaveValue("")); // form.reset() after the 201
    expect(screen.getByLabelText("Role")).toHaveTextContent("Select role");       // the controlled Select reset too
  });
});
