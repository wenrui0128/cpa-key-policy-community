package policy

import (
	"encoding/json"
	"fmt"
	"time"
)

type OfficialCycle struct {
	Account string `json:"account"`
	Start   int64  `json:"start"`
	End     int64  `json:"end"`
}
type CycleEvent struct {
	At          time.Time `json:"at"`
	Alias       string    `json:"alias"`
	Amount      float64   `json:"amount"`
	Cache       float64   `json:"cache"`
	CacheTokens int64     `json:"cache_tokens"`
	Input       int64     `json:"input"`
	Output      int64     `json:"output"`
	Calls       int64     `json:"calls"`
}
type CycleArchive struct {
	Cycle OfficialCycle `json:"cycle"`
	Usage UsageWindow   `json:"usage"`
}

func addCycleEvent(w *UsageWindow, e CycleEvent) {
	w.TotalUSD += e.Amount
	w.CacheCostUSD += e.Cache
	w.CacheReadTokens += e.CacheTokens
	w.InputTokens += e.Input
	w.OutputTokens += e.Output
	w.CallCount += e.Calls
}
func applyOfficialCycle(st *UsageState, c OfficialCycle, now time.Time) error {
	if c.Account == "" || c.Start <= 0 || c.End-c.Start != 604800 || c.Start > now.Unix() || c.End <= now.Unix() {
		return fmt.Errorf("Invalid or expired official cycle")
	}
	if st.Cycle == nil {
		st.Cycle = &c
		st.Weekly.WindowStart = time.Unix(c.Start, 0).UTC()
		return nil
	} // First adoption preserves existing usage.
	old := *st.Cycle
	if old.Account != c.Account {
		return fmt.Errorf("Account changed; manual review required")
	}
	if c.End < old.End {
		return fmt.Errorf("Cycle rollback rejected")
	}
	if c.End == old.End {
		if c.Start != old.Start {
			return fmt.Errorf("Conflicting cycle start")
		}
		return nil
	}
	// All events are recorded at completion; replay those occurring after the new boundary.
	// This preserves post-reset consumption accumulated while confirmation was pending.
	previous := st.Weekly
	for _, e := range st.Events {
		if e.At.Unix() >= c.Start {
			previous.TotalUSD -= e.Amount
			previous.CacheCostUSD -= e.Cache
			previous.CacheReadTokens -= e.CacheTokens
			previous.InputTokens -= e.Input
			previous.OutputTokens -= e.Output
			previous.CallCount -= e.Calls
		}
	}
	st.History = append(st.History, CycleArchive{Cycle: old, Usage: previous})
	st.Cycle = &c
	st.Weekly = UsageWindow{WindowStart: time.Unix(c.Start, 0).UTC()}
	day := now.UTC().Truncate(dayWindow)
	if day.Before(time.Unix(c.Start, 0)) {
		day = time.Unix(c.Start, 0).UTC()
	}
	st.Daily = UsageWindow{WindowStart: day}
	st.ByAlias = map[string]AliasUsageWindows{}
	events := st.Events
	st.Events = nil
	for _, e := range events {
		if e.At.Unix() < c.Start {
			continue
		}
		st.Events = append(st.Events, e)
		addCycleEvent(&st.Weekly, e)
		a := st.ByAlias[e.Alias]
		a.Weekly.WindowStart = st.Weekly.WindowStart
		addCycleEvent(&a.Weekly, e)
		if !e.At.Before(day) {
			addCycleEvent(&st.Daily, e)
			a.Daily.WindowStart = day
			addCycleEvent(&a.Daily, e)
		}
		st.ByAlias[e.Alias] = a
	}
	return nil
}
func (s *Store) SyncOfficialCycle(c OfficialCycle) error {
	s.updateMu.Lock()
	defer s.updateMu.Unlock()
	keys := s.Keys()
	s.persistMu.Lock()
	defer s.persistMu.Unlock()
	_, l := s.runtimeComponents()
	if l == nil {
		return fmt.Errorf("Usage ledger unavailable")
	}
	path := s.StatePath()
	l.mu.Lock()
	defer l.mu.Unlock()
	// Prepare every transition before changing memory or writing the ledger.
	snapshot := map[string]*UsageState{}
	for id, v := range l.entries {
		snapshot[id] = v
	}
	for _, key := range keys {
		old := l.entries[key.ID]
		if old == nil {
			old = &UsageState{}
		}
		raw, err := json.Marshal(old)
		if err != nil {
			return err
		}
		var next UsageState
		if err = json.Unmarshal(raw, &next); err != nil {
			return err
		}
		if err = applyOfficialCycle(&next, c, l.now()); err != nil {
			return fmt.Errorf("Key %s: %w", key.ID, err)
		}
		snapshot[key.ID] = &next
	}
	// Validate even when no keys exist; retain the confirmed cycle for new keys.
	if err := applyOfficialCycle(&UsageState{}, c, l.now()); err != nil {
		return err
	}
	if err := SaveUsageOnly(path, snapshot); err != nil {
		return err
	}
	l.entries = snapshot
	l.officialCycle = &c
	return nil
}
func (s *Store) OfficialCycleStatus() map[string]any {
	keys := s.Keys()
	_, l := s.runtimeComponents()
	if l == nil {
		return map[string]any{"enabled": false}
	}
	l.mu.Lock()
	defer l.mu.Unlock()
	var cycle *OfficialCycle
	var history []CycleArchive
	states := map[string]any{}
	managed := []string{}
	for _, key := range keys {
		st := l.entries[key.ID]
		if st == nil {
			continue
		}
		states[key.ID] = map[string]any{"cycle": st.Cycle, "history": st.History}
		if st.Cycle != nil {
			managed = append(managed, key.ID)
			if cycle == nil {
				cycle = st.Cycle
				history = st.History
			}
		}
	}
	raw, _ := json.Marshal(map[string]any{"enabled": cycle != nil, "scope": "all_plugin_keys", "managed_keys": managed, "cycle": cycle, "history": history, "keys": states})
	var result map[string]any
	_ = json.Unmarshal(raw, &result)
	return result
}
