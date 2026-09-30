// HARNESS PROBE (not from the archetypes): tsc can't see Nest DI errors, so this is compiled with decorator
// metadata and RUN. A module that uses @UseGuards(JwtAuthGuard) must compile once JWT_CONFIG is provided.
// (Before the JWT_CONFIG token existed: "Nest can't resolve dependencies of the JwtAuthGuard (?, Reflector)".)
import "reflect-metadata";
import { Controller, Get, UseGuards } from "@nestjs/common";
import { Test } from "@nestjs/testing";
import { JWT_CONFIG, JwtAuthGuard } from "./guards/jwt-auth.guard";
import type { JwtConfig } from "./types/auth";

@Controller("probe")
@UseGuards(JwtAuthGuard)
class ProbeController {
  @Get()
  ok() {
    return { ok: true };
  }
}

async function main(): Promise<void> {
  const jwtConfig: JwtConfig = { secret: "probe-only", issuer: "https://issuer.test", audience: "api", algorithms: ["HS256"] };
  const moduleRef = await Test.createTestingModule({
    controllers: [ProbeController],
    providers: [{ provide: JWT_CONFIG, useValue: jwtConfig }],
  }).compile();
  const app = moduleRef.createNestApplication({ logger: false });
  await app.init();
  const guard = moduleRef.get(JwtAuthGuard);
  await app.close();
  console.log(`Nest DI: ${guard.constructor.name} resolved with JWT_CONFIG`);
}

main().catch((e: unknown) => {
  console.error("Nest DI FAILED:", e instanceof Error ? e.message : e);
  process.exit(1);
});
