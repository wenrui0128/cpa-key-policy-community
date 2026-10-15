package plugin

import (
	"os"
	"testing"
)

// NewApp initializes a default ledger before host configuration arrives.
// Keep that runtime file outside the checkout during every test invocation.
func TestMain(m *testing.M) {
	directory, err := os.MkdirTemp("", "key-policy-tests-")
	if err != nil {
		panic(err)
	}
	if err := os.Chdir(directory); err != nil {
		panic(err)
	}
	status := m.Run()
	_ = os.RemoveAll(directory)
	os.Exit(status)
}
