# gomock patterns for Go mock generation and verification.

## Generate Mocks
```bash
# Install mockgen
go install go.uber.org/mock/mockgen@latest

# From interface in source file
mockgen -source=internal/service/user.go -destination=internal/service/mocks/mock_user.go -package=mocks

# From interface by name (reflection mode)
mockgen -destination=internal/service/mocks/mock_repo.go -package=mocks github.com/org/repo/internal/service UserRepository

# go:generate directive — place in the file that defines the interface
//go:generate mockgen -source=user.go -destination=mocks/mock_user.go -package=mocks
```
- Regenerate mocks after any interface change
- Keep mocks in a `mocks/` subdirectory alongside the interface package

## Basic Mock Setup
```go
func TestCreateUser(t *testing.T) {
    ctrl := gomock.NewController(t)
    // ctrl.Finish() called automatically via t.Cleanup in Go 1.14+

    mockRepo := mocks.NewMockUserRepository(ctrl)
    mockMailer := mocks.NewMockMailer(ctrl)

    svc := service.NewUserService(mockRepo, mockMailer)

    mockRepo.EXPECT().
        Save(gomock.Any(), gomock.Eq(&domain.User{Name: "alice"})).
        Return(nil)

    mockMailer.EXPECT().
        Send(gomock.Any(), gomock.Any()).
        Return(nil)

    err := svc.CreateUser(context.Background(), "alice")
    assert.NoError(t, err)
}
```

## EXPECT Patterns
```go
// Exact argument match
mockRepo.EXPECT().FindByID(gomock.Any(), "user-123").Return(&user, nil)

// Any argument
mockRepo.EXPECT().Save(gomock.Any(), gomock.Any()).Return(nil)

// Custom matcher
mockRepo.EXPECT().Save(gomock.Any(), gomock.Cond(func(x any) bool {
    u, ok := x.(*domain.User)
    return ok && u.Email != ""
})).Return(nil)

// Return error
mockRepo.EXPECT().FindByID(gomock.Any(), "bad-id").Return(nil, service.ErrNotFound)
```

## Call Count Controls
```go
mockRepo.EXPECT().Save(gomock.Any(), gomock.Any()).Times(1)        // exactly once (default)
mockRepo.EXPECT().Ping(gomock.Any()).AnyTimes()                     // zero or more
mockRepo.EXPECT().Log(gomock.Any()).MinTimes(1)                     // at least once
mockRepo.EXPECT().Log(gomock.Any()).MaxTimes(3)                     // at most 3
```

## Ordered Calls
```go
// Enforce call order with InOrder
gomock.InOrder(
    mockRepo.EXPECT().BeginTx(gomock.Any()).Return(tx, nil),
    mockRepo.EXPECT().Save(gomock.Any(), gomock.Any()).Return(nil),
    mockRepo.EXPECT().CommitTx(gomock.Any()).Return(nil),
)
```

## Do / DoAndReturn
```go
// Side effect without changing return
mockRepo.EXPECT().Save(gomock.Any(), gomock.Any()).
    Do(func(ctx context.Context, u *domain.User) {
        assert.NotEmpty(t, u.ID) // verify ID was set before save
    }).Return(nil)

// Compute return value dynamically
mockRepo.EXPECT().FindByID(gomock.Any(), gomock.Any()).
    DoAndReturn(func(ctx context.Context, id string) (*domain.User, error) {
        return &domain.User{ID: id, Name: "test"}, nil
    })
```

## Rules
- One `gomock.NewController(t)` per test — never share across subtests
- Unmatched EXPECT calls fail the test automatically at cleanup
- Prefer `gomock.Any()` for context arguments — tests should not assert on context values
- Use `gomock.Eq()` for value comparisons, `gomock.Nil()` for nil checks
- Keep mock expectations close to the function call they verify
