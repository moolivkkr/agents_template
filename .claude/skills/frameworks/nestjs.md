# NestJS patterns for structured, testable Node.js APIs.

## Module Structure
```
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
@Controller("users")
@UseGuards(JwtAuthGuard)
export class UsersController {
    constructor(private readonly usersService: UsersService) {}

    @Post()
    @HttpCode(HttpStatus.CREATED)
    async create(@Body() dto: CreateUserDto): Promise<UserResponseDto> {
        return this.usersService.create(dto)
    }
}
```
- No business logic in controllers
- `@Body()` with class-validator DTOs for auto-validation
- `@UseGuards()` at controller or method level

## DTOs with Validation
```typescript
export class CreateUserDto {
    @IsEmail()
    email: string

    @MinLength(8)
    password: string
}
```
Enable global `ValidationPipe`:
```typescript
app.useGlobalPipes(new ValidationPipe({ whitelist: true, transform: true }))
```

## Services
```typescript
@Injectable()
export class UsersService {
    constructor(private readonly repo: UsersRepository) {}

    async create(dto: CreateUserDto): Promise<User> {
        const existing = await this.repo.findByEmail(dto.email)
        if (existing) throw new ConflictException("Email already in use")
        return this.repo.create(dto)
    }
}
```

## Testing
```typescript
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
})
```

## Rules
- `@Injectable()` on all providers — enables DI
- `ConfigService` for env vars — never `process.env` directly in services
- Exception filters for domain error → HTTP mapping
- `@nestjs/swagger` for API docs — annotate DTOs with `@ApiProperty()`
