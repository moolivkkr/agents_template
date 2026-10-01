// HARNESS STUB: shadcn/ui Input (project code copied into components/ui).
import * as React from "react";
import { cn } from "@/lib/utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return <input type={type} data-slot="input" className={cn("h-9 w-full rounded-md border px-3 py-1", className)} {...props} />;
}

export { Input };
