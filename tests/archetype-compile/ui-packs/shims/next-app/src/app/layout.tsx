// HARNESS STUB (app-level): the root layout every App Router app has, wrapping pages in the Providers from
// ui/api-integration-patterns.md (components/providers.tsx).
import type { ReactNode } from "react";
import { Providers } from "@/components/providers";

export const metadata = { title: "ui-packs harness" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <main id="main-content">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
