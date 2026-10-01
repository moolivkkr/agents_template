// HARNESS SMOKE TEST (tests/archetype-compile/go) — not archetype code.
// Checks performance-go.md 1.3 against the pinned go-redis: when the reply to an INCR is lost (it
// arrives after ReadTimeout), NewRedisClient re-sends it and the counter moves twice, while
// NewRedisNoRetryClient sends it once and reports the error. The fake server below speaks just
// enough RESP2 for the handshake (unknown commands get an error reply) and INCR.

package cache

import (
	"bufio"
	"context"
	"fmt"
	"net"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/redis/go-redis/v9"
)

type fakeRedis struct {
	ln         net.Listener
	incrs      atomic.Int64 // INCRs the server executed
	delayFirst time.Duration
	once       sync.Once
}

func startFakeRedis(t *testing.T, delayFirst time.Duration) *fakeRedis {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	f := &fakeRedis{ln: ln, delayFirst: delayFirst}
	t.Cleanup(func() { _ = ln.Close() })
	go func() {
		for {
			c, err := ln.Accept()
			if err != nil {
				return
			}
			go f.serve(c)
		}
	}()
	return f
}

func (f *fakeRedis) serve(c net.Conn) {
	defer c.Close()
	rd := bufio.NewReader(c)
	for {
		args, err := readCommand(rd)
		if err != nil {
			return
		}
		switch strings.ToUpper(args[0]) {
		case "PING":
			fmt.Fprint(c, "+PONG\r\n")
		case "INCR":
			n := f.incrs.Add(1) // executed: the effect happens whether or not the reply arrives
			f.once.Do(func() { time.Sleep(f.delayFirst) })
			fmt.Fprintf(c, ":%d\r\n", n)
		default:
			fmt.Fprintf(c, "-ERR unknown command '%s'\r\n", args[0])
		}
	}
}

func readCommand(rd *bufio.Reader) ([]string, error) {
	line, err := rd.ReadString('\n')
	if err != nil {
		return nil, err
	}
	n, err := strconv.Atoi(strings.TrimSpace(strings.TrimPrefix(line, "*")))
	if err != nil || n < 1 {
		return nil, fmt.Errorf("bad array header %q", line)
	}
	args := make([]string, n)
	for i := range args {
		hdr, err := rd.ReadString('\n')
		if err != nil {
			return nil, err
		}
		size, err := strconv.Atoi(strings.TrimSpace(strings.TrimPrefix(hdr, "$")))
		if err != nil {
			return nil, err
		}
		buf := make([]byte, size+2)
		if _, err := ioReadFull(rd, buf); err != nil {
			return nil, err
		}
		args[i] = string(buf[:size])
	}
	return args, nil
}

func ioReadFull(rd *bufio.Reader, buf []byte) (int, error) {
	n := 0
	for n < len(buf) {
		m, err := rd.Read(buf[n:])
		n += m
		if err != nil {
			return n, err
		}
	}
	return n, nil
}

// The doc's clients use ReadTimeout 3s; the first INCR reply arrives after 3.5s.
const lostReply = 3500 * time.Millisecond

func TestRetryingClientRepeatsALostINCR(t *testing.T) {
	srv := startFakeRedis(t, lostReply)
	rdb := NewRedisClient(srv.ln.Addr().String(), "")
	defer rdb.Close()

	got, err := rdb.Incr(context.Background(), "counter").Result()
	if err != nil {
		t.Fatalf("INCR: %v", err)
	}
	if got != 2 || srv.incrs.Load() != 2 {
		t.Fatalf("INCR returned %d, server ran it %d times; want the documented double apply (2, 2)", got, srv.incrs.Load())
	}
}

func TestNoRetryClientSendsINCROnce(t *testing.T) {
	srv := startFakeRedis(t, lostReply)
	rdb := NewRedisNoRetryClient(srv.ln.Addr().String(), "")
	defer rdb.Close()

	if _, err := rdb.Incr(context.Background(), "counter").Result(); err == nil {
		t.Fatal("INCR with a lost reply returned no error")
	}
	time.Sleep(200 * time.Millisecond) // let any (wrong) re-send arrive
	if n := srv.incrs.Load(); n != 1 {
		t.Fatalf("server ran INCR %d times, want 1", n)
	}
}

// The doc says MaxRetries 0 does not disable retries (it means "default", 3): pin that.
func TestMaxRetriesZeroStillRetries(t *testing.T) {
	srv := startFakeRedis(t, lostReply)
	opts := redisOptions(srv.ln.Addr().String(), "")
	opts.MaxRetries = 0
	rdb := redis.NewClient(opts)
	defer rdb.Close()

	if got, err := rdb.Incr(context.Background(), "counter").Result(); err != nil || got != 2 {
		t.Fatalf("MaxRetries 0: INCR = %d, %v; want a retry (2)", got, err)
	}
}
