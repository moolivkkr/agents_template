// HARNESS SMOKE TEST (tests/archetype-compile/go) — not archetype code.
// Drives websocket-pattern-go.md's hub over a real connection: upgrade with a ticket, subscribe,
// receive the ack, and get a message broadcast by a second client. The earlier sample started both
// pumps as goroutines on r.Context(), which net/http cancels when the handler returns, so the socket
// closed straight after the upgrade.

package ws

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/coder/websocket"
	"github.com/coder/websocket/wsjson"
)

func dial(t *testing.T, ctx context.Context, url, ticket string) *websocket.Conn {
	t.Helper()
	c, _, err := websocket.Dial(ctx, url+"?ticket="+ticket, nil)
	if err != nil {
		t.Fatalf("dial: %v", err)
	}
	t.Cleanup(func() { _ = c.CloseNow() })
	return c
}

func expect(t *testing.T, ctx context.Context, c *websocket.Conn, typ string) Message {
	t.Helper()
	var m Message
	if err := wsjson.Read(ctx, c, &m); err != nil {
		t.Fatalf("waiting for %q: %v", typ, err)
	}
	if m.Type != typ {
		t.Fatalf("got message %+v, want type %q", m, typ)
	}
	return m
}

func TestHubUpgradeSubscribeBroadcast(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	hub := NewHub(slog.New(slog.DiscardHandler))
	go hub.Run(ctx)
	srv := httptest.NewServer(http.HandlerFunc(hub.HandleUpgrade))
	defer srv.Close()
	url := "ws" + strings.TrimPrefix(srv.URL, "http")

	// No ticket: rejected before the upgrade.
	if _, _, err := websocket.Dial(ctx, url+"?ticket=nope", nil); err == nil {
		t.Fatal("dial with an unknown ticket succeeded")
	}

	a := dial(t, ctx, url, testTicket)
	b := dial(t, ctx, url, testTicket)
	sub, _ := json.Marshal(map[string]string{"room": "tenant-1:general"})
	for i, c := range []*websocket.Conn{a, b} {
		ref := []string{"a1", "b1"}[i]
		if err := wsjson.Write(ctx, c, Message{Type: "subscribe", Payload: sub, Ref: ref}); err != nil {
			t.Fatalf("subscribe: %v", err)
		}
		if ack := expect(t, ctx, c, "ack"); ack.Ref != ref {
			t.Fatalf("ack ref = %q, want %q", ack.Ref, ref)
		}
	}

	msg, _ := json.Marshal(map[string]any{"room": "tenant-1:general", "data": map[string]string{"text": "hi"}})
	if err := wsjson.Write(ctx, a, Message{Type: "message", Payload: msg, Ref: "a2"}); err != nil {
		t.Fatalf("send: %v", err)
	}
	expect(t, ctx, a, "ack")
	got := expect(t, ctx, b, "message")
	if got.Room != "tenant-1:general" || !strings.Contains(string(got.Payload), "hi") {
		t.Fatalf("b received %+v", got)
	}
}
