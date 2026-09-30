// HARNESS STUB (tests/archetype-compile/go) — not archetype code.
// worker-pattern-go.md uses the project's queue message type, domain.Job, without defining it.

package domain

type Job struct {
	ID       string
	Type     string // e.g. "email.send"
	TenantID string
	Attempt  int // 1-based
	Payload  []byte
}
