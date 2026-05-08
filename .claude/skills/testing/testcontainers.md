# testcontainers-go patterns for container-based integration testing.

## Install
```bash
go get github.com/testcontainers/testcontainers-go
go get github.com/testcontainers/testcontainers-go/modules/postgres
go get github.com/testcontainers/testcontainers-go/modules/redis
```

## PostgreSQL Container
```go
func TestWithPostgres(t *testing.T) {
    ctx := context.Background()

    pgContainer, err := postgres.Run(ctx,
        "postgres:16-alpine",
        postgres.WithDatabase("testdb"),
        postgres.WithUsername("test"),
        postgres.WithPassword("test"),
        testcontainers.WithWaitStrategy(
            wait.ForLog("database system is ready to accept connections").
                WithOccurrence(2).
                WithStartupTimeout(30*time.Second),
        ),
    )
    require.NoError(t, err)
    t.Cleanup(func() { require.NoError(t, pgContainer.Terminate(ctx)) })

    connStr, err := pgContainer.ConnectionString(ctx, "sslmode=disable")
    require.NoError(t, err)

    // Use the connection string with your DB layer
    db, err := pgxpool.New(ctx, connStr)
    require.NoError(t, err)
    defer db.Close()

    // Run migrations
    runMigrations(t, connStr)

    // Test your repository
    repo := repository.NewUserRepository(db)
    err = repo.Save(ctx, &domain.User{Name: "alice"})
    assert.NoError(t, err)
}
```

## Redis Container
```go
func TestWithRedis(t *testing.T) {
    ctx := context.Background()

    redisContainer, err := redis.Run(ctx,
        "redis:7-alpine",
        testcontainers.WithWaitStrategy(
            wait.ForLog("Ready to accept connections").
                WithStartupTimeout(15*time.Second),
        ),
    )
    require.NoError(t, err)
    t.Cleanup(func() { require.NoError(t, redisContainer.Terminate(ctx)) })

    endpoint, err := redisContainer.Endpoint(ctx, "")
    require.NoError(t, err)

    client := goredis.NewClient(&goredis.Options{Addr: endpoint})
    defer client.Close()

    // Test your cache layer
    cache := cache.NewRedisCache(client)
    err = cache.Set(ctx, "key", "value", time.Minute)
    assert.NoError(t, err)
}
```

## Shared Test Helper
```go
// testutil/containers.go — reuse across test files
func NewTestDB(t *testing.T) *pgxpool.Pool {
    t.Helper()
    ctx := context.Background()

    pgContainer, err := postgres.Run(ctx,
        "postgres:16-alpine",
        postgres.WithDatabase("testdb"),
        postgres.WithUsername("test"),
        postgres.WithPassword("test"),
        postgres.WithInitScripts("../../migrations/init.sql"),
        testcontainers.WithWaitStrategy(
            wait.ForLog("database system is ready to accept connections").
                WithOccurrence(2).WithStartupTimeout(30*time.Second),
        ),
    )
    require.NoError(t, err)
    t.Cleanup(func() { _ = pgContainer.Terminate(ctx) })

    connStr, err := pgContainer.ConnectionString(ctx, "sslmode=disable")
    require.NoError(t, err)

    pool, err := pgxpool.New(ctx, connStr)
    require.NoError(t, err)
    t.Cleanup(func() { pool.Close() })

    return pool
}
```

## Custom Container (Generic)
```go
req := testcontainers.ContainerRequest{
    Image:        "localstack/localstack:latest",
    ExposedPorts: []string{"4566/tcp"},
    Env:          map[string]string{"SERVICES": "s3,sqs"},
    WaitingFor:   wait.ForHTTP("/_localstack/health").WithPort("4566/tcp"),
}
container, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
    ContainerRequest: req,
    Started:          true,
})
require.NoError(t, err)
t.Cleanup(func() { _ = container.Terminate(ctx) })

host, _ := container.Host(ctx)
port, _ := container.MappedPort(ctx, "4566")
endpoint := fmt.Sprintf("http://%s:%s", host, port.Port())
```

## Rules
- Always use `t.Cleanup` for container teardown — never `defer` in test helpers
- Use `WithStartupTimeout` to avoid flaky CI failures from slow container starts
- Gate integration tests with `//go:build integration` or check for `INTEGRATION_TEST` env var
- Reuse helper functions (like `NewTestDB`) — don't duplicate container setup across tests
- Use `WithInitScripts` to apply migrations instead of running them manually
- Prefer module packages (`postgres.Run`, `redis.Run`) over raw `GenericContainer` when available
