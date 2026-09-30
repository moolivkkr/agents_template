// HARNESS STUB (tests/archetype-compile/go) — not archetype code.
// crud-repository-test-go.md's optional cache tests call newTestRedis(t) and leave the choice to the
// project ("in-memory Redis mock or real testcontainers Redis"). This is the in-memory choice.

package postgres

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"
)

type memRedis struct {
	mu   sync.Mutex
	data map[string][]byte
}

func newTestRedis(t *testing.T) RedisClient {
	t.Helper()
	return &memRedis{data: map[string][]byte{}}
}

func (m *memRedis) Get(_ context.Context, key string) ([]byte, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	v, ok := m.data[key]
	if !ok {
		return nil, errors.New("miss")
	}
	return v, nil
}

func (m *memRedis) Set(_ context.Context, key string, value []byte, _ time.Duration) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.data[key] = value
	return nil
}

func (m *memRedis) Delete(_ context.Context, key string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	delete(m.data, key)
	return nil
}
