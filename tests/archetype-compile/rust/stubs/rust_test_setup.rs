// HARNESS STUB — testing/rust-test.md "Async Tests with Tokio" calls setup_test_service(), the reader's
// helper. This one wires the real WidgetService to the archetypes' mocks behaving like an empty store:
// create succeeds, every lookup misses. The service logic under test is the archetype's.
pub(crate) async fn setup_test_service() -> WidgetService {
    let mut repo = MockWidgetRepository::new();
    repo.expect_create().returning(|_| Ok(()));
    repo.expect_get_by_id().returning(|_, _| Err(AppError::NotFound { resource: "Widget" }));
    let mut cache = MockCache::new();
    cache.expect_get().returning(|_| Ok(None));
    cache.expect_set().returning(|_, _, _| Ok(()));
    let mut audit = MockAuditWriter::new();
    audit.expect_write().returning(|_| Ok(()));
    WidgetService::new(Arc::new(repo), Arc::new(cache), Arc::new(audit))
}
