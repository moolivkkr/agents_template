// HARNESS STUB: the shadcn/ui components the page archetypes render. In a project these are the
// generated files under components/ui/; only their prop shapes matter for type-checking.
import type { ComponentProps, ReactNode } from "react";

export function Skeleton(props: ComponentProps<"div">) {
  return <div {...props} />;
}

export function Card(props: ComponentProps<"div">) {
  return <div {...props} />;
}

export function CardContent(props: ComponentProps<"div">) {
  return <div {...props} />;
}

export function Tabs(props: { value?: string; onValueChange?: (value: string) => void; children?: ReactNode }) {
  return <div>{props.children}</div>;
}

export function TabsContent(props: { value: string; children?: ReactNode }) {
  return <div>{props.children}</div>;
}

export function FormSkeleton(props: { fields: number }) {
  return <div aria-busy="true" data-fields={props.fields} />;
}
