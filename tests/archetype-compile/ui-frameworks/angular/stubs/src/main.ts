// HARNESS STUB: the CLI's standard bootstrap (angular.md shows app.config.ts and app.ts).
import { bootstrapApplication } from "@angular/platform-browser"
import { App } from "./app/app"
import { appConfig } from "./app/app.config"

bootstrapApplication(App, appConfig).catch((err: unknown) => console.error(err))
