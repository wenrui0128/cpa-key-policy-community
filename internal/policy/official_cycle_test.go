package policy

import (
	"encoding/json"
	"testing"
	"time"
)

func TestOfficialCyclePreservesAdoptionAndIdempotence(t *testing.T) {
	n := time.Unix(1800000000, 0)
	c := OfficialCycle{"account", n.Unix() - 100, n.Unix() - 100 + 604800}
	s := UsageState{Weekly: UsageWindow{TotalUSD: 7}}
	if err := applyOfficialCycle(&s, c, n); err != nil {
		t.Fatal(err)
	}
	if s.Weekly.TotalUSD != 7 {
		t.Fatal("initial adoption cleared usage")
	}
	if err := applyOfficialCycle(&s, c, n); err != nil || s.Weekly.TotalUSD != 7 {
		t.Fatal("duplicate cleared usage")
	}
}
func TestOfficialCycleReplayPreservesPostResetUsage(t *testing.T) {
	n := time.Unix(1800000000, 0)
	old := OfficialCycle{"account", n.Unix() - 604900, n.Unix() - 100}
	s := UsageState{Cycle: &old, Weekly: UsageWindow{TotalUSD: 9}, Events: []CycleEvent{{At: n.Add(-200 * time.Second), Alias: "m", Amount: 7}, {At: n.Add(-50 * time.Second), Alias: "m", Amount: 2}}}
	c := OfficialCycle{"account", n.Unix() - 100, n.Unix() - 100 + 604800}
	if err := applyOfficialCycle(&s, c, n); err != nil {
		t.Fatal(err)
	}
	if s.Weekly.TotalUSD != 2 || s.Daily.TotalUSD != 2 || s.History[0].Usage.TotalUSD != 7 {
		t.Fatalf("bad replay: %+v", s)
	}
	raw, _ := json.Marshal(s)
	var restored UsageState
	if err := json.Unmarshal(raw, &restored); err != nil {
		t.Fatal(err)
	}
	if restored.Cycle.End != c.End || len(restored.Events) != 1 || len(restored.History) != 1 {
		t.Fatal("cycle state lost on reload")
	}
}
func TestOfficialCycleRejectsRollbackAndAccountChange(t *testing.T) {
	n := time.Unix(1800000000, 0)
	old := OfficialCycle{"a", n.Unix() - 100, n.Unix() - 100 + 604800}
	s := UsageState{Cycle: &old}
	bad := old
	bad.Account = "b"
	if applyOfficialCycle(&s, bad, n) == nil {
		t.Fatal("account switch accepted")
	}
	bad = old
	bad.End--
	bad.Start--
	if applyOfficialCycle(&s, bad, n) == nil {
		t.Fatal("rollback accepted")
	}
}
func TestOfficialCycleDoesNotAutomaticallyExpire(t *testing.T) {
	n := time.Unix(1800000000, 0)
	c := OfficialCycle{"a", n.Unix() - 700000, n.Unix() - 95200}
	l := newUsageLedger(func() time.Time { return n })
	l.entries["demo-key"] = &UsageState{Cycle: &c, Weekly: UsageWindow{TotalUSD: 20}}
	got := l.Summary(KeyConfig{ID: "demo-key", WeeklyLimitUSD: 20})
	if got.WeeklyUSD != 20 || got.WeeklyResetAt.Unix() != c.End {
		t.Fatal("expired official cycle cleared without confirmation")
	}
}
func TestOfficialCycleConcurrentBudgetEditsAndFlush(t *testing.T) {
	n := time.Unix(1800000000, 0)
	s := NewStore()
	s.SetClock(func() time.Time { return n })
	key := KeyConfig{ID: "demo-key", Enabled: true, KeyHash: hashForUsageTest(t, "test-key"), WeeklyLimitUSD: 20, Models: []ModelRule{{Alias: "m", Provider: "openai", TargetModel: "m", InputPricePerMillion: 1}}}
	if err := s.Configure(Config{Enabled: true, StateFile: t.TempDir() + "/state.json", Keys: []KeyConfig{key}}); err != nil {
		t.Fatal(err)
	}
	c := OfficialCycle{"a", n.Unix() - 100, n.Unix() - 100 + 604800}
	done := make(chan error, 3)
	go func() {
		for i := 0; i < 40; i++ {
			if e := s.SyncOfficialCycle(c); e != nil {
				done <- e
				return
			}
		}
		done <- nil
	}()
	go func() {
		for i := 0; i < 40; i++ {
			if e := s.UpsertKey(key, true); e != nil {
				done <- e
				return
			}
		}
		done <- nil
	}()
	go func() {
		for i := 0; i < 40; i++ {
			s.RecordUsage("demo-key", "m", "m", false, UsageDetail{InputTokens: 1000})
			if e := s.FlushUsage(); e != nil {
				done <- e
				return
			}
		}
		done <- nil
	}()
	for i := 0; i < 3; i++ {
		select {
		case e := <-done:
			if e != nil {
				t.Fatal(e)
			}
		case <-time.After(10 * time.Second):
			t.Fatal("concurrent operations deadlocked")
		}
	}
	if s.UsageSummaryFor(s.Keys()[0]).WeeklyUSD < 0.0399 {
		t.Fatal("lost accounted usage")
	}
}
func TestAllKeysCycleAndNewKeyInheritance(t *testing.T) {
	n := time.Unix(1800000000, 0)
	s := NewStore()
	s.SetClock(func() time.Time { return n })
	key := func(id string) KeyConfig {
		return KeyConfig{ID: id, Enabled: true, KeyHash: hashForUsageTest(t, id), WeeklyLimitUSD: 100, Models: []ModelRule{{Alias: "m", Provider: "openai", TargetModel: "m", InputPricePerMillion: 1}}}
	}
	path := t.TempDir() + "/state.json"
	if err := s.Configure(Config{Enabled: true, StateFile: path, Keys: []KeyConfig{key("a"), key("b")}}); err != nil {
		t.Fatal(err)
	}
	s.RecordUsage("a", "m", "m", false, UsageDetail{InputTokens: 1000000})
	s.RecordUsage("b", "m", "m", false, UsageDetail{InputTokens: 2000000})
	c := OfficialCycle{"account", n.Unix() - 100, n.Unix() - 100 + 604800}
	if err := s.SyncOfficialCycle(c); err != nil {
		t.Fatal(err)
	}
	if s.UsageSummaryFor(key("a")).WeeklyUSD != 1 || s.UsageSummaryFor(key("b")).WeeklyUSD != 2 {
		t.Fatal("adoption erased spend")
	}
	if err := s.UpsertKey(key("new"), true); err != nil {
		t.Fatal(err)
	}
	got := s.UsageSummaryFor(key("new"))
	if got.WeeklyResetAt.Unix() != c.End {
		t.Fatal("new key did not inherit cycle")
	}
	if err := s.FlushUsage(); err != nil {
		t.Fatal(err)
	}
	restored := NewStore()
	restored.SetClock(func() time.Time { return n })
	if err := restored.Configure(Config{Enabled: true, StateFile: path}); err != nil {
		t.Fatal(err)
	}
	if err := restored.UpsertKey(key("after-restart"), true); err != nil {
		t.Fatal(err)
	}
	if restored.UsageSummaryFor(key("after-restart")).WeeklyResetAt.Unix() != c.End {
		t.Fatal("cycle inheritance lost on restart")
	}
	n = n.Add(604800 * time.Second)
	s.RecordUsage("b", "m", "m", false, UsageDetail{InputTokens: 3000000})
	next := OfficialCycle{"account", c.Start + 604800, c.End + 604800}
	if err := s.SyncOfficialCycle(next); err != nil {
		t.Fatal(err)
	}
	if s.UsageSummaryFor(key("a")).WeeklyUSD != 0 || s.UsageSummaryFor(key("b")).WeeklyUSD != 3 {
		t.Fatal("all-key reset/replay failed")
	}
}
func TestAllKeyCycleTransitionIsAtomic(t *testing.T) {
	n := time.Unix(1800000000, 0)
	s := NewStore()
	s.SetClock(func() time.Time { return n })
	keys := []KeyConfig{{ID: "a", Enabled: true, KeyHash: hashForUsageTest(t, "a")}, {ID: "b", Enabled: true, KeyHash: hashForUsageTest(t, "b")}}
	if err := s.Configure(Config{Enabled: true, StateFile: t.TempDir() + "/state.json", Keys: keys}); err != nil {
		t.Fatal(err)
	}
	c := OfficialCycle{"account", n.Unix() - 100, n.Unix() - 100 + 604800}
	if err := s.SyncOfficialCycle(c); err != nil {
		t.Fatal(err)
	}
	_, l := s.runtimeComponents()
	l.mu.Lock()
	l.entries["b"].Cycle.Account = "different"
	l.mu.Unlock()
	n = n.Add(604800 * time.Second)
	next := OfficialCycle{"account", c.Start + 604800, c.End + 604800}
	if s.SyncOfficialCycle(next) == nil {
		t.Fatal("conflicting account accepted")
	}
	l.mu.Lock()
	defer l.mu.Unlock()
	if l.entries["a"].Cycle.End != c.End {
		t.Fatal("partial cycle update on failure")
	}
}
