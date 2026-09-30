// HARNESS STUB: the root module that auth-middleware-typescript.md's main.ts bootstraps.
import { Module } from "@nestjs/common";
import { WidgetModule } from "./modules/widget/widget.module";

@Module({ imports: [WidgetModule] })
export class AppModule {}
