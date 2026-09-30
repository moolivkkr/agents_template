// HARNESS STUB: the form component under test in ui/archetypes/component-test.md (the project's own code).
export function WidgetForm(props: { onSuccess?: () => void }) {
  return <form onSubmit={() => props.onSuccess?.()} />;
}
