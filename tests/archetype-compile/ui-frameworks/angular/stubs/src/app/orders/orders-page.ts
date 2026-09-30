// HARNESS STUB: a page hosting angular.md's OrderList, with the <h1 tabindex="-1"> focus target.
import { ChangeDetectionStrategy, Component, inject } from "@angular/core"
import { Router } from "@angular/router"
import { t } from "../i18n"
import { OrderList } from "./order-list"

@Component({
  selector: "app-orders-page",
  imports: [OrderList],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1 tabindex="-1">{{ t("orders.title") }}</h1>
    <app-order-list (create)="router.navigate(['/orders/new'])" />
  `,
})
export class OrdersPage {
  protected readonly router = inject(Router)
  protected readonly t = t
}
