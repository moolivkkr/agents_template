// HARNESS STUB (app-level form): the CreateUserForm testing/msw.md's request-assertion test drives — a Name
// field and a Create button that POSTs the payload itself (requests aren't wrapped in the envelope).
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

export function CreateUserForm() {
  const [name, setName] = useState("");
  const create = useMutation({
    mutationFn: (input: { name: string }) =>
      fetch("/api/v1/users", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input) }),
  });
  return (
    <form onSubmit={(e) => { e.preventDefault(); create.mutate({ name }); }}>
      <label htmlFor="name">Name</label>
      <input id="name" value={name} onChange={(e) => setName(e.target.value)} />
      <button type="submit">Create</button>
    </form>
  );
}
