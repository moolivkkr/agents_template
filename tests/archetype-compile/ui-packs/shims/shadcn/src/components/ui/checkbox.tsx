// HARNESS STUB: shadcn/ui Checkbox (project code copied into components/ui), on the radix-ui Checkbox primitive.
"use client";
import * as React from "react";
import { Checkbox as CheckboxPrimitive } from "radix-ui";
import { cn } from "@/lib/utils";

function Checkbox({ className, ...props }: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root data-slot="checkbox" className={cn("size-4 shrink-0 rounded-[4px] border", className)} {...props}>
      <CheckboxPrimitive.Indicator data-slot="checkbox-indicator" />
    </CheckboxPrimitive.Root>
  );
}

export { Checkbox };
