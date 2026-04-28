# Rust patterns and conventions for safe, performant applications.

## Project Structure
```
src/
  main.rs         # binary entry point
  lib.rs          # library root (if dual crate)
  domain/
  services/
  repositories/
  api/
  error.rs        # unified error types
Cargo.toml
```

## Error Handling
```rust
// Library errors: thiserror
#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error("user not found: {id}")]
    UserNotFound { id: Uuid },
    #[error("database error: {0}")]
    Database(#[from] sqlx::Error),
}

// Application errors: anyhow (for main/bin crates)
fn run() -> anyhow::Result<()> {
    let config = load_config().context("failed to load config")?;
    Ok(())
}
```
- `thiserror` for library/domain errors (structured, typed)
- `anyhow` for application/binary error propagation
- Never `.unwrap()` or `.expect()` in production code — only in tests or provably unreachable

## Ownership
- Prefer `&str` over `String` in function parameters when ownership isn't needed
- Use `Arc<T>` for shared ownership across threads; `Rc<T>` only for single-thread
- `Cow<'_, str>` when sometimes borrowing, sometimes owning

## Async (tokio)
```rust
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tokio::spawn(background_task());
    // ...
}
```
- `tokio::spawn` for independent concurrent tasks
- `tokio::join!` for concurrent awaits that all must succeed
- Never block inside async — use `tokio::task::spawn_blocking` for CPU work

## Testing
```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_email_valid() {
        assert!(Email::parse("user@example.com").is_ok());
    }

    #[tokio::test]
    async fn test_user_service_create() { ... }
}
```
- Tests in the same file as the code (`mod tests`)
- Integration tests in `tests/` directory
- `#[should_panic]` for explicit panic tests only

## Rules
- `#![deny(warnings)]` in CI (not in library crate root)
- Run `clippy -- -D warnings` in CI
- `rustfmt` for formatting — no manual style debates
- `cargo audit` for dependency vulnerability scanning
- Feature flags in `Cargo.toml` for optional dependencies
