// HARNESS PROBE PAGE (app-level): one element per token utility the packs use, the shadcn Button, and
// ui/component-composition.md's Alert in every variant. e2e/theme.spec.ts reads their computed styles.
import { Alert } from "@/components/common/alert";
import { Button } from "@/components/ui/button";

const SAMPLES: Array<[string, string]> = [
  ["bg-background", "bg-background text-foreground"],
  ["bg-primary", "bg-primary text-primary-foreground"],
  ["bg-secondary", "bg-secondary text-secondary-foreground"],
  ["bg-card", "bg-card text-card-foreground"],
  ["bg-muted", "bg-muted text-muted-foreground"],
  ["bg-accent", "bg-accent text-accent-foreground"],
  ["bg-destructive", "bg-destructive text-white"],
  ["bg-warning", "bg-warning"],
  ["bg-success", "bg-success"],
  ["bg-primary-50", "bg-primary/50"],
  ["border-border", "border border-border"],
  ["rounded-lg", "rounded-lg border"],
];

export default function ThemeProbe() {
  return (
    <main className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Theme probe</h1>
      {SAMPLES.map(([id, className]) => (
        <div key={id} data-testid={id} className={className}>
          {id}
        </div>
      ))}
      <Button data-testid="button">Save</Button>
      <section aria-label="Alerts" data-testid="alerts" className="space-y-3">
        <Alert variant="default" title="Note" description="A plain notice." />
        <Alert variant="destructive" title="Payment failed" description="The card was declined." />
        <Alert variant="warning" title="Trial ending" description="Your trial ends in 3 days." />
        <Alert variant="success" title="Saved" description="Your changes are live." />
      </section>
    </main>
  );
}
