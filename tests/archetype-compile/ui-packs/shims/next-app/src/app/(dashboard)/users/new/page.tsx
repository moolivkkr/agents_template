// HARNESS STUB (app-level): a client form that calls frameworks/nextjs.md's createUser Server Action through
// React's useActionState — `next build` and tsc then prove the action's (prevState, formData) signature and its
// { details } result, the same details[] shape as the API's 400 VALIDATION_FAILED.
"use client";
import { useActionState } from "react";
import { createUser } from "../actions";

export default function NewUserPage() {
  const [state, formAction, pending] = useActionState(createUser, { details: [] });
  return (
    <form action={formAction}>
      <label htmlFor="name">Name</label>
      <input id="name" name="name" />
      <label htmlFor="email">Email</label>
      <input id="email" name="email" type="email" />
      <label htmlFor="role">Role</label>
      <select id="role" name="role" defaultValue="member">
        <option value="admin">Admin</option>
        <option value="member">Member</option>
        <option value="viewer">Viewer</option>
      </select>
      {state.details.map((d) => (
        <p key={d.field} role="alert">{d.message}</p>
      ))}
      <button type="submit" disabled={pending}>Create user</button>
    </form>
  );
}
