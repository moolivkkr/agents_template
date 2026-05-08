# testify patterns for Go testing.

## Assert vs Require
```go
// require — stops test immediately on failure (use for setup/preconditions)
require.NoError(t, err)
require.NotNil(t, result)

// assert — logs failure but continues (use for multiple assertions)
assert.Equal(t, expected, actual)
assert.Contains(t, list, item)
assert.ErrorIs(t, err, ErrNotFound)
```
- Use `require` for preconditions that would make later assertions meaningless
- Use `assert` for the actual test checks — see all failures at once

## Table-Driven Tests
```go
func TestValidateEmail(t *testing.T) {
    tests := []struct {
        name  string
        input string
        want  bool
    }{
        {"valid email", "user@example.com", true},
        {"missing @", "userexample.com", false},
        {"empty string", "", false},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got := ValidateEmail(tt.input)
            assert.Equal(t, tt.want, got)
        })
    }
}
```
- Name each case — shows in test output
- Use `t.Run` for subtests — can run individually with `-run`

## Suite Pattern
```go
type ServiceTestSuite struct {
    suite.Suite
    db   *pgxpool.Pool
    svc  *CertService
}

func (s *ServiceTestSuite) SetupSuite() {
    s.db = testutil.NewTestDB(s.T())
    s.svc = NewCertService(s.db)
}

func (s *ServiceTestSuite) TestCreate() {
    cert, err := s.svc.Create(ctx, req)
    s.Require().NoError(err)
    s.Assert().Equal("active", cert.Status)
}

func TestServiceSuite(t *testing.T) {
    suite.Run(t, new(ServiceTestSuite))
}
```
- Use suites for shared setup (DB connections, services)
- `SetupSuite` runs once, `SetupTest` runs per test

## Error Testing
```go
assert.ErrorIs(t, err, ErrNotFound)           // check error chain
assert.ErrorAs(t, err, &domainErr)             // extract typed error
assert.ErrorContains(t, err, "not found")      // check message
assert.NoError(t, err)                          // no error expected
```

## HTTP Handler Testing
```go
func TestHandler(t *testing.T) {
    req := httptest.NewRequest("GET", "/api/v1/certs", nil)
    rec := httptest.NewRecorder()
    handler.ServeHTTP(rec, req)

    assert.Equal(t, http.StatusOK, rec.Code)
    var resp ApiResponse
    require.NoError(t, json.NewDecoder(rec.Body).Decode(&resp))
    assert.NotNil(t, resp.Data)
}
```
