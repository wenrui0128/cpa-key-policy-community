package policy

import (
	"testing"
	"time"
)

func TestRateLimiter(t *testing.T) {
	now := time.Date(2026, 6, 28, 0, 0, 0, 0, time.UTC)
	limiter := NewRateLimiterWithClock(func() time.Time { return now })
	if !limiter.Allow("team-a", 2) {
		t.Fatal("first request denied")
	}
	if !limiter.Allow("team-a", 2) {
		t.Fatal("second request denied")
	}
	if limiter.Allow("team-a", 2) {
		t.Fatal("third request allowed")
	}
	now = now.Add(time.Minute)
	if !limiter.Allow("team-a", 2) {
		t.Fatal("request after window denied")
	}
}
