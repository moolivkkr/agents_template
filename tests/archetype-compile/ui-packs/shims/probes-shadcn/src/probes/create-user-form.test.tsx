// HARNESS PROBE: renders ui/shadcn.md's Field + Controller form: it submits once every schema field is valid,
// and an invalid field shows its FieldError (role="alert") and aria-invalid.
import "@testing-library/jest-dom/vitest";
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CreateUserForm } from "@/components/create-user-form";

describe("shadcn.md — CreateUserForm", () => {
  it("submits the values once both fields are valid, and shows field errors until then", async () => {
    const onCreate = vi.fn();
    const user = userEvent.setup();
    render(<CreateUserForm onCreate={onCreate} />);
    await user.type(screen.getByLabelText("Email"), "alice@example.com");
    await user.type(screen.getByLabelText("Name"), "A");
    await user.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByText("Name must be at least 2 characters")).toHaveAttribute("role", "alert");
    expect(screen.getByLabelText("Name")).toHaveAttribute("aria-invalid", "true");
    expect(onCreate).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText("Name"), "lice");
    await user.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(1));
    expect(onCreate.mock.calls[0]?.[0]).toEqual({ email: "alice@example.com", name: "Alice" });
  });
});
