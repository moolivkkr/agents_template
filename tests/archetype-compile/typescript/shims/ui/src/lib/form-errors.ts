// HARNESS STUB mirroring ui/error-handling-patterns.md §Server Validation Error Mapping.
import type { FieldValues, Path, UseFormReturn } from "react-hook-form";
import type { FieldError } from "../types/api";

export function mapServerErrors<T extends FieldValues>(form: UseFormReturn<T>, details: FieldError[]): boolean {
  let mapped = false;
  for (const d of details) {
    if (d.field in form.getValues()) {
      form.setError(d.field as Path<T>, { type: "server", message: d.message });
      mapped = true;
    }
  }
  return mapped;
}
