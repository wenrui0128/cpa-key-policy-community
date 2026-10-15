package policy

import (
	"net/http"
	"testing"
)

func TestHashAndMatchKey(t *testing.T) {
	hash, err := HashKey("cpa_secret")
	if err != nil {
		t.Fatalf("HashKey() error = %v", err)
	}
	if !MatchHash("cpa_secret", hash) {
		t.Fatal("MatchHash() = false, want true")
	}
	if MatchHash("wrong", hash) {
		t.Fatal("MatchHash() = true for wrong key")
	}
}

func TestExtractAPIKey(t *testing.T) {
	cases := []struct {
		name    string
		headers http.Header
		query   map[string][]string
		want    string
	}{
		{
			name:    "bearer",
			headers: http.Header{"Authorization": []string{"Bearer cpa_123"}},
			want:    "cpa_123",
		},
		{
			name:    "x-api-key",
			headers: http.Header{"X-API-Key": []string{"cpa_456"}},
			want:    "cpa_456",
		},
		{
			name:  "query",
			query: map[string][]string{"api_key": {"cpa_789"}},
			want:  "cpa_789",
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := ExtractAPIKey(tc.headers, tc.query); got != tc.want {
				t.Fatalf("ExtractAPIKey() = %q, want %q", got, tc.want)
			}
		})
	}
}

func TestPreviewKey(t *testing.T) {
	if got := PreviewKey("cpa_abcdefghijklmnopqrstuvwxyz"); got != "cpa_abc...vwxyz" {
		t.Fatalf("PreviewKey() = %q", got)
	}
}

func TestPreviewDoesNotExposeShortCredentials(t *testing.T) {
	for _, key := range []string{"k", "cpa_secret", "twelve-chars", "cpa_thirteen1", "twenty-four-chars-secret"} {
		got := PreviewKey(key)
		if got == key || len(got) == 0 {
			t.Fatalf("preview must not contain the complete short credential")
		}
	}
}

func TestLegacyStoredPreviewsCannotRevealCompleteKey(t *testing.T) {
	for _, secret := range []string{"short-key", "cpa_secret", "a-longer-custom-secret"} {
		hash, _ := HashKey(secret)
		for _, preview := range []string{secret, secret + "..."} {
			if got := SafeStoredPreview(preview, hash); got != "[redacted]" {
				t.Fatal("stored plaintext credential must be masked")
			}
		}
	}

	secret := "cpa_abcdefghijklmnopqrstuvwxyz"
	hash, _ := HashKey(secret)
	preview := PreviewKey(secret)
	if got := SafeStoredPreview(preview, hash); got != preview {
		t.Fatal("a partial generated preview should remain readable")
	}
}
