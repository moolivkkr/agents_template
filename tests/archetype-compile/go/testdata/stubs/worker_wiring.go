// HARNESS STUB (tests/archetype-compile/go) — not archetype code.
// The worker main's "your queue implementation" / "your idempotency store" wiring, the config it
// reads, and the services its example handlers call. Signatures follow how the samples use them.

package main

import (
	"context"
	"time"

	"yourapp/internal/domain"
	"yourapp/internal/worker"
)

type config struct {
	RedisURL          string
	WorkerConcurrency int
	JobTimeout        time.Duration
	ShutdownTimeout   time.Duration
}

var cfg config

func newRedisQueue(url string) worker.Queue                  { return nil }
func newRedisIdempotency(url string) worker.IdempotencyStore { return nil }
func newEmailService(c config) EmailService                  { return nil }
func newReportService(c config) ReportService                { return nil }

type EmailService interface {
	RenderTemplate(ctx context.Context, templateID string, vars map[string]any) (string, error)
	Send(ctx context.Context, to, subject, html string) error
}

type EmailPayload struct {
	TemplateID string         `json:"template_id"`
	Variables  map[string]any `json:"variables"`
	To         string         `json:"to"`
	Subject    string         `json:"subject"`
}

type ReportService interface {
	Generate(ctx context.Context, job *domain.Job) error
}

type ReportGenerateHandler struct{ svc ReportService }

func (h *ReportGenerateHandler) Type() string { return "report.generate" }
func (h *ReportGenerateHandler) Handle(ctx context.Context, job *domain.Job) error {
	return h.svc.Generate(ctx, job)
}
