// HARNESS STUB: the app shell angular.md §6 describes (skip link + <main> + router outlet).
import { ChangeDetectionStrategy, Component } from "@angular/core"
import { RouterOutlet } from "@angular/router"
import { t } from "./i18n"

@Component({
  selector: "app-root",
  imports: [RouterOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <a href="#main" class="sr-only focus:not-sr-only">{{ t("a11y.skipToContent") }}</a>
    <main id="main"><router-outlet /></main>
  `,
})
export class App {
  protected readonly t = t
}
