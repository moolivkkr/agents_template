// HARNESS STUB (app-level): the root layout importing app/globals.css, whose content is the token CSS of
// ui/tailwind.md (generated file + app tokens) and ui/shadcn.md (overrides), extracted at run time.
import type { ReactNode } from "react";
import "./globals.css";

export const metadata = { title: "Theme probe" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
