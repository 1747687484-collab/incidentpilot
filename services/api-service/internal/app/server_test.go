package app

import "testing"

func TestSplitContent(t *testing.T) {
	content := "one two three four five six"
	chunks := splitContent(content, 2)
	if len(chunks) != 3 {
		t.Fatalf("expected 3 chunks, got %d", len(chunks))
	}
	if chunks[0] != "one two" || chunks[2] != "five six" {
		t.Fatalf("unexpected chunks: %#v", chunks)
	}
}

func TestEmbeddingLiteral(t *testing.T) {
	got := embeddingLiteral("payment timeout latency")
	if got == "" || got[0] != '[' || got[len(got)-1] != ']' {
		t.Fatalf("invalid vector literal: %q", got)
	}
}

