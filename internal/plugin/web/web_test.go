package web

import (
	"net/http"
	"testing"
)

func TestServeIndex(t *testing.T) {
	status, headers, body := Serve("/index.html")
	if status != http.StatusOK {
		t.Fatalf("status = %d, want 200", status)
	}
	if got := headers.Get("Content-Type"); got != "text/html; charset=utf-8" {
		t.Fatalf("content-type = %q, want text/html", got)
	}
	if len(body) == 0 {
		t.Fatal("body is empty")
	}
	if string(body[:min(len(body), 15)]) == "" {
		t.Fatal("body not a string")
	}
	// Embedded file should be an HTML document.
	if !contains(body, "<!doctype html>") && !contains(body, "<!DOCTYPE html>") {
		t.Fatalf("body does not look like html: %s", string(body[:40]))
	}
}

func TestServeTrailingSlashTrimmed(t *testing.T) {
	status, _, _ := Serve("/index.html/")
	if status != http.StatusOK {
		t.Fatalf("status = %d, want 200 (trailing slash trimmed)", status)
	}
}

func TestServeUnknownPath404(t *testing.T) {
	status, _, _ := Serve("/assets/app.js")
	if status != http.StatusNotFound {
		t.Fatalf("status = %d, want 404", status)
	}
}

func TestManagementUIHasPrivacyAndFramingHeaders(t *testing.T) {
	_, headers, _ := Serve("/index.html")
	for name, want := range map[string]string{
		"Cache-Control":           "no-store",
		"Referrer-Policy":         "no-referrer",
		"X-Content-Type-Options":  "nosniff",
		"Content-Security-Policy": "frame-ancestors 'self'; base-uri 'none'; object-src 'none'",
	} {
		if got := headers.Get(name); got != want {
			t.Fatalf("%s = %q, want %q", name, got, want)
		}
	}
}

func contains(haystack []byte, needle string) bool {
	return len(haystack) >= len(needle) && indexOf(haystack, []byte(needle)) >= 0
}

func indexOf(h, n []byte) int {
outer:
	for i := 0; i <= len(h)-len(n); i++ {
		for j := 0; j < len(n); j++ {
			if h[i+j] != n[j] {
				continue outer
			}
		}
		return i
	}
	return -1
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
