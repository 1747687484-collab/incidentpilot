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

func TestParseIncidentListLimit(t *testing.T) {
	tests := []struct {
		name    string
		raw     string
		want    int
		wantErr bool
	}{
		{name: "default", raw: "", want: 20},
		{name: "custom", raw: "5", want: 5},
		{name: "too low", raw: "0", wantErr: true},
		{name: "too high", raw: "101", wantErr: true},
		{name: "not number", raw: "many", wantErr: true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := parseIncidentListLimit(tt.raw)
			if tt.wantErr {
				if err == nil {
					t.Fatalf("expected error")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if got != tt.want {
				t.Fatalf("expected %d, got %d", tt.want, got)
			}
		})
	}
}

func TestValidIncidentStatus(t *testing.T) {
	if !validIncidentStatus("awaiting_approval") {
		t.Fatalf("expected awaiting_approval to be valid")
	}
	if validIncidentStatus("deleted") {
		t.Fatalf("expected deleted to be invalid")
	}
}
