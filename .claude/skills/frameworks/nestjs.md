# NestJS patterns for structured, testable Node.js APIs.

> TypeScript samples compile-checked 2026-09-30: TS 7.0.2 strict + noUncheckedIndexedAccess (legacy decorators), NestJS 12.1, class-validator 0.15, Jest 30 types, against the guard, decorator, error and filter modules of the backend archetypes; the spec is type-checked only (tests/archetype-compile/typescript/run.sh).

The full stack (guards, error filter, CRUD controller, DTOs) is `backend/archetypes/*-typescript.md`.
NestJS needs `"experimentalDecorators": true` and `"emitDecoratorMetadata": true` in tsconfig.json.

## Module Structure
```text
src/
  users/
    users.module.ts
    users.controller.ts
    users.service.ts
    users.repository.ts
    dto/create-user.dto.ts
    dto/user-response.dto.ts
  auth/
    auth.module.ts
  app.module.ts
```
One module per feature. Import only what's needed — avoid `SharedModule` anti-pattern.

## Controller
```typescript
// src/users/users.controller.ts
import { Body, Controller, HttpCode, HttpStatus, Post, UseGuards } from "@nestjs/common"
import { CurrentUser } from "../decorators/current-user.decorator"
import { JwtAuthGuard } from "../guards/jwt-auth.guard"
import type { AuthUser } from "../types/auth"
import { CreateUserDto } from "./dto/create-user.dto"
import type { UserResponseDto } from "./dto/user-response.dto"
import { UsersService } from "./users.service"

@Controller("users")
@UseGuards(JwtAuthGuard)
export class UsersController {
    constructor(private readonly usersService: UsersService) {}

    @Post()
    @HttpCode(HttpStatus.CREATED)
    async create(@CurrentUser() user: AuthUser, @Body() dto: CreateUserDto): Promise<UserResponseDto> {
        return this.usersService.create(user.tenantId, dto) // tenant from the verified token, never the body
    }
}
```
- No business logic in controllers
- `@Body()` with class-validator DTOs for auto-validation
- `@UseGuards()` at controller or method level

## DTOs with Validation
```typescript
// src/users/dto/create-user.dto.ts
import { IsEmail, IsString, MaxLength, MinLength } from "class-validator"

export class CreateUserDto {
    @IsEmail()
    email!: string // `!`: class-transformer fills it from the body, not a constructor

    @IsString()
    @MinLength(8)
    @MaxLength(128)
    password!: string
}
```
The global `ValidationPipe` is the archetype's `appValidationPipe()`: its `exceptionFactory` makes a failure
400 `VALIDATION_FAILED` with `details[]` in the envelope — not Nest's default `{ statusCode, message, error }`
body. `configureApp(app)` (`src/app.setup.ts`, backend/archetypes/auth-middleware-typescript.md) installs it
with the error filter, the request id and the body limit, for `main.ts` and every e2e test alike:
```typescript
// inside configureApp(app) — never a hand-built ValidationPipe elsewhere
app.useGlobalPipes(appValidationPipe()) // whitelist, forbidNonWhitelisted, transform, exceptionFactory
app.useGlobalFilters(new AppErrorFilter())
```

## Services
```typescript
// src/users/users.service.ts
import { Injectable } from "@nestjs/common"
import { conflict } from "../errors/domain-errors"
import type { CreateUserDto } from "./dto/create-user.dto"
import { toUserResponse, type UserResponseDto } from "./dto/user-response.dto"
import { UsersRepository } from "./users.repository"

@Injectable()
export class UsersService {
    constructor(private readonly repo: UsersRepository) {}

    async create(tenantId: string, dto: CreateUserDto): Promise<UserResponseDto> {
        const existing = await this.repo.findByEmail(tenantId, dto.email)
        // a domain error: the global AppErrorFilter writes the envelope (Nest's ConflictException would not)
        if (existing) throw conflict("A user with this email already exists.")
        return toUserResponse(await this.repo.create(tenantId, dto)) // the response DTO never carries the hash
    }
}
```

## Testing
```typescript
// src/users/users.service.spec.ts
import { Test } from "@nestjs/testing"
import { UsersRepository, type User } from "./users.repository"
import { UsersService } from "./users.service"

describe("UsersService", () => {
    let service: UsersService
    let repo: jest.Mocked<UsersRepository>

    beforeEach(async () => {
        const module = await Test.createTestingModule({
            providers: [
                UsersService,
                { provide: UsersRepository, useValue: { findByEmail: jest.fn(), create: jest.fn() } },
            ],
        }).compile()
        service = module.get(UsersService)
        repo = module.get(UsersRepository)
    })

    it("rejects an email already used in the tenant with CONFLICT", async () => {
        const existing: User = { id: "u-1", tenantId: "t-1", email: "a@example.com", passwordHash: "x", createdAt: new Date() }
        repo.findByEmail.mockResolvedValue(existing)

        await expect(service.create("t-1", { email: "a@example.com", password: "a-long-password" }))
            .rejects.toMatchObject({ code: "CONFLICT", status: 409 })
        expect(repo.create).not.toHaveBeenCalled()
    })
})
```

## Rules
- `@Injectable()` on all providers — enables DI
- `ConfigService` for env vars — never `process.env` directly in services
- Exception filters for domain error → HTTP mapping
- `@nestjs/swagger` for API docs — annotate DTOs with `@ApiProperty()`
