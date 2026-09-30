// HARNESS STUB: a project's sign-in page (angular.md's routes lazy-load it).
import { ChangeDetectionStrategy, Component } from "@angular/core"
import { t } from "../i18n"

@Component({
  selector: "app-login-page",
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<h1 tabindex="-1">{{ t("login.title") }}</h1>`,
})
export class LoginPage {
  protected readonly t = t
}
