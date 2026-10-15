package plugin

import (
	"encoding/json"
	"net/http"
	"testing"
)

// An upstream overload for one model can leave the account's aggregate status
// at "error" while CPA still includes it for this model. Use only CPA's pool.
func TestSchedulerHistoricalErrorUsesCPACandidate(t *testing.T) {
	for _, status := range []string{"error", " ERROR "} {
		t.Run(status, func(t *testing.T) {
			app, plain := configureTestApp(t)
			request := SchedulerPickRequest{
				Provider: "codex", Model: "gpt-5-codex",
				Options: SchedulerPickOptions{Headers: map[string][]string{
					"Authorization": {"Bearer " + plain},
				}},
				Candidates: []SchedulerAuthCandidate{{ID: "eligible", Provider: "codex", Status: status}},
			}
			picked := schedulerPickForTest(t, app, request)
			if picked.AuthID != "eligible" {
				t.Fatalf("expected CPA-provided candidate, got %+v", picked)
			}
		})
	}
}

func TestSchedulerHistoricalErrorPreservesGroupAndWeights(t *testing.T) {
	app, _ := configureTestApp(t)
	request := SchedulerPickRequest{
		Provider: "codex", Model: "gpt-5-codex",
		Options: SchedulerPickOptions{Metadata: map[string]any{"group": "pro"}},
		Candidates: []SchedulerAuthCandidate{
			{ID: "error-pro", Provider: "codex", Status: "error", Priority: 5, Weight: 2, Attributes: map[string]string{"plan_type": "pro"}},
			{ID: "active-pro", Provider: "codex", Status: "active", Priority: 5, Weight: 1, Attributes: map[string]string{"plan_type": "pro"}},
			{ID: "wrong-group", Provider: "codex", Status: "error", Priority: 99, Weight: 100, Attributes: map[string]string{"plan_type": "plus"}},
			{ID: "low-priority", Provider: "codex", Status: "error", Priority: 1, Weight: 100, Attributes: map[string]string{"plan_type": "pro"}},
			{ID: "zero-weight", Provider: "codex", Status: "error", Priority: 99, Weight: 0, Attributes: map[string]string{"plan_type": "pro"}},
		},
	}
	counts := map[string]int{}
	for i := 0; i < 9; i++ {
		counts[schedulerPickForTest(t, app, request).AuthID]++
	}
	if len(counts) != 2 || counts["error-pro"] != 6 || counts["active-pro"] != 3 {
		t.Fatalf("group, priority and 2:1 weights must still apply, got %v", counts)
	}
}

func TestSchedulerHistoricalErrorDoesNotFallBackToWrongGroup(t *testing.T) {
	app, _ := configureTestApp(t)
	request := SchedulerPickRequest{
		Provider: "codex", Model: "gpt-5-codex",
		Options:    SchedulerPickOptions{Metadata: map[string]any{"group": "pro"}},
		Candidates: []SchedulerAuthCandidate{{ID: "plus-only", Provider: "codex", Status: "error", Attributes: map[string]string{"plan_type": "plus"}}},
	}
	assertSchedulerUnavailable(t, app, request)
}

func TestSchedulerHistoricalErrorFixPreservesUnavailableStates(t *testing.T) {
	for _, status := range []string{
		"disabled", "expired", "revoked", "invalid", "unavailable", "cooldown",
		"cooling_down", "quota_exhausted", "exhausted", "blocked", " DISABLED ", "cooling-down",
	} {
		t.Run(status, func(t *testing.T) {
			app, plain := configureTestApp(t)
			request := SchedulerPickRequest{
				Provider: "codex", Model: "gpt-5-codex",
				Options:    SchedulerPickOptions{Headers: map[string][]string{"Authorization": {"Bearer " + plain}}},
				Candidates: []SchedulerAuthCandidate{{ID: "unusable", Provider: "codex", Status: status}},
			}
			assertSchedulerUnavailable(t, app, request)
			request.Candidates = append(request.Candidates, SchedulerAuthCandidate{ID: "eligible", Provider: "codex", Status: "error"})
			if picked := schedulerPickForTest(t, app, request); picked.AuthID != "eligible" {
				t.Fatalf("unusable candidate must remain excluded, got %+v", picked)
			}
		})
	}
}

func TestSchedulerHistoricalErrorWithNoPositiveWeightStillFails(t *testing.T) {
	app, plain := configureTestApp(t)
	request := SchedulerPickRequest{
		Provider: "codex", Model: "gpt-5-codex",
		Options:    SchedulerPickOptions{Headers: map[string][]string{"Authorization": {"Bearer " + plain}}},
		Candidates: []SchedulerAuthCandidate{{ID: "paused", Provider: "codex", Status: "error", Weight: 0}},
	}
	assertSchedulerUnavailable(t, app, request)
}

func TestSchedulerHistoricalErrorFixDoesNotInventCandidatesOrHandleNativeKeys(t *testing.T) {
	for _, native := range []bool{false, true} {
		t.Run(map[bool]string{false: "empty-cpa-pool", true: "native-key"}[native], func(t *testing.T) {
			app, plain := configureTestApp(t)
			request := SchedulerPickRequest{Provider: "codex", Model: "gpt-5-codex"}
			if native {
				plain = "native-key"
				request.Candidates = []SchedulerAuthCandidate{{ID: "eligible", Provider: "codex", Status: "error"}}
			}
			request.Options.Headers = map[string][]string{"Authorization": {"Bearer " + plain}}
			envelope := schedulerEnvelopeForErrorTest(t, app, request)
			var picked SchedulerPickResponse
			if !envelope.OK || json.Unmarshal(envelope.Result, &picked) != nil || picked.Handled || picked.AuthID != "" {
				t.Fatalf("must defer to CPA without creating a candidate, got %+v / %+v", envelope, picked)
			}
		})
	}
}

func TestSchedulerHistoricalErrorFixPreservesBudgetDenial(t *testing.T) {
	app, plain := configurePricedApp(t)
	request := SchedulerPickRequest{
		Provider: "codex", Model: "gpt-5-codex",
		Options:    SchedulerPickOptions{Headers: map[string][]string{"Authorization": {"Bearer " + plain}}},
		Candidates: []SchedulerAuthCandidate{{ID: "eligible", Provider: "codex", Status: "error"}},
	}
	if schedulerPickForTest(t, app, request).AuthID != "eligible" {
		t.Fatal("expected eligible historical-error candidate")
	}
	usage, err := json.Marshal(UsageHandleRequest{
		APIKey: "priced", Alias: "fast", Model: "gpt-5-codex",
		Detail: UsageDetail{InputTokens: 1_000_000, TotalTokens: 1_000_000},
	})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := app.HandleMethod(MethodUsageHandle, usage); err != nil {
		t.Fatal(err)
	}
	decision := app.Store().Authenticate("POST", "/v1/responses", http.Header(request.Options.Headers), nil, []byte(`{"model":"fast"}`))
	if decision.Allowed || !decision.CostLimited || decision.Reason != "daily_exceeded" {
		t.Fatalf("historical error must not bypass budget admission, got %+v", decision)
	}
}

func schedulerEnvelopeForErrorTest(t *testing.T, app *App, request SchedulerPickRequest) Envelope {
	t.Helper()
	raw, err := json.Marshal(request)
	if err != nil {
		t.Fatal(err)
	}
	raw, err = app.HandleMethod(MethodSchedulerPick, raw)
	if err != nil {
		t.Fatal(err)
	}
	var envelope Envelope
	if err := json.Unmarshal(raw, &envelope); err != nil {
		t.Fatal(err)
	}
	return envelope
}

func assertSchedulerUnavailable(t *testing.T, app *App, request SchedulerPickRequest) {
	t.Helper()
	envelope := schedulerEnvelopeForErrorTest(t, app, request)
	if envelope.OK || envelope.Error == nil || envelope.Error.Code != "auth_not_found" || envelope.Error.HTTPStatus != http.StatusServiceUnavailable {
		t.Fatalf("expected unavailable scheduler envelope, got %+v", envelope)
	}
}
