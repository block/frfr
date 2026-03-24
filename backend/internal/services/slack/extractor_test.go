package slack

import (
	"context"
	"testing"
)

// newTestExtractor creates an extractor with a pre-populated user cache and no real API client.
func newTestExtractor(users map[string]string) *Extractor {
	e := NewExtractor("xoxb-fake", 1000, 90)
	for k, v := range users {
		e.userCache[k] = v
	}
	return e
}

func TestCleanSlackMarkup_UserMentions(t *testing.T) {
	e := newTestExtractor(map[string]string{"U123ABC": "alice"})
	ctx := context.Background()

	tests := []struct {
		name  string
		input string
		want  string
	}{
		{"resolved mention", "<@U123ABC> said hello", "@alice said hello"},
		{"cached mention", "<@U123ABC> and <@U123ABC>", "@alice and @alice"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := e.cleanSlackMarkup(ctx, tt.input)
			if got != tt.want {
				t.Errorf("got %q, want %q", got, tt.want)
			}
		})
	}
}

func TestCleanSlackMarkup_Links(t *testing.T) {
	e := newTestExtractor(nil)
	ctx := context.Background()

	tests := []struct {
		name  string
		input string
		want  string
	}{
		{"labeled link", "<https://example.com|Example Site>", "Example Site (https://example.com)"},
		{"bare link", "<https://example.com/path>", "https://example.com/path"},
		{"link with query params", "<https://example.com?foo=bar|click here>", "click here (https://example.com?foo=bar)"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := e.cleanSlackMarkup(ctx, tt.input)
			if got != tt.want {
				t.Errorf("got %q, want %q", got, tt.want)
			}
		})
	}
}

func TestCleanSlackMarkup_Channels(t *testing.T) {
	e := newTestExtractor(nil)
	ctx := context.Background()

	tests := []struct {
		name  string
		input string
		want  string
	}{
		{"labeled channel", "<#C0123ABCDEF|general>", "#general"},
		{"bare channel", "<#C0123ABCDEF>", "#C0123ABCDEF"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := e.cleanSlackMarkup(ctx, tt.input)
			if got != tt.want {
				t.Errorf("got %q, want %q", got, tt.want)
			}
		})
	}
}

func TestCleanSlackMarkup_HTMLEntities(t *testing.T) {
	e := newTestExtractor(nil)
	ctx := context.Background()

	tests := []struct {
		name  string
		input string
		want  string
	}{
		{"ampersand", "A &amp; B", "A & B"},
		{"less than", "x &lt; y", "x < y"},
		{"greater than", "x &gt; y", "x > y"},
		{"all entities", "&lt;div&gt; &amp; stuff", "<div> & stuff"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := e.cleanSlackMarkup(ctx, tt.input)
			if got != tt.want {
				t.Errorf("got %q, want %q", got, tt.want)
			}
		})
	}
}

func TestCleanSlackMarkup_PreservesEmoji(t *testing.T) {
	e := newTestExtractor(nil)
	ctx := context.Background()

	tests := []struct {
		name  string
		input string
		want  string
	}{
		{"wave emoji", ":wave: hello", ":wave: hello"},
		{"thumbsup", "looks good :+1:", "looks good :+1:"},
		{"multiple emoji", ":fire: :rocket: shipped", ":fire: :rocket: shipped"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := e.cleanSlackMarkup(ctx, tt.input)
			if got != tt.want {
				t.Errorf("got %q, want %q", got, tt.want)
			}
		})
	}
}

func TestCleanSlackMarkup_Combined(t *testing.T) {
	e := newTestExtractor(map[string]string{"U999TESTID": "alice"})
	ctx := context.Background()

	input := ":wave: Hey <@U999TESTID>, check out <https://example.com/metrics|project metrics> &amp; <#C0123ABCDEF|data-team>"
	want := ":wave: Hey @alice, check out project metrics (https://example.com/metrics) & #data-team"

	got := e.cleanSlackMarkup(ctx, input)
	if got != want {
		t.Errorf("got %q, want %q", got, want)
	}
}

func TestParseSlackTimestamp(t *testing.T) {
	tests := []struct {
		name string
		ts   string
		unix int64
	}{
		{"standard", "1762447128.235749", 1762447128},
		{"round", "1700000000.000000", 1700000000},
		{"no decimal", "1234567890", 1234567890},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := parseSlackTimestamp(tt.ts)
			if got.Unix() != tt.unix {
				t.Errorf("got unix %d, want %d", got.Unix(), tt.unix)
			}
		})
	}
}

func TestBuildPermalink(t *testing.T) {
	got := buildPermalink("general", "C0123ABCDEF", "1762447128.235749")
	want := "https://slack.com/archives/C0123ABCDEF/p1762447128235749"
	if got != want {
		t.Errorf("got %q, want %q", got, want)
	}
}

func TestBuildThreadPermalink(t *testing.T) {
	got := buildThreadPermalink("general", "C0123ABCDEF", "1762448407.712439", "1762447128.235749")
	want := "https://slack.com/archives/C0123ABCDEF/p1762448407712439?thread_ts=1762447128.235749&cid=C0123ABCDEF"
	if got != want {
		t.Errorf("got %q, want %q", got, want)
	}
}

func TestExtractOptions_VolumeProbeDefaults(t *testing.T) {
	// Verify that NewExtractor stores config values correctly
	e := NewExtractor("xoxb-fake", 500, 30)
	if e.maxMessages != 500 {
		t.Errorf("maxMessages: got %d, want 500", e.maxMessages)
	}
	if e.lookbackDays != 30 {
		t.Errorf("lookbackDays: got %d, want 30", e.lookbackDays)
	}
}
