package slack

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"
)

// ExtractionResult contains the result of Slack channel text extraction.
type ExtractionResult struct {
	Status       string `json:"status"`
	Method       string `json:"method"`
	ChannelID    string `json:"channel_id"`
	ChannelName  string `json:"channel_name"`
	MessageCount int    `json:"message_count"`
	ThreadCount  int    `json:"thread_count"`
	TotalChars   int    `json:"total_chars"`
	OutputFile   string `json:"output_file"`
	Error        string `json:"error,omitempty"`
	ErrorType    string `json:"error_type,omitempty"`
}

// ExtractOptions configures what to extract from a Slack channel.
type ExtractOptions struct {
	Since          time.Time
	Until          time.Time
	IncludeThreads bool
}

// Extractor handles text extraction from Slack channels.
type Extractor struct {
	client       *Client
	userCache    map[string]string // userID -> display name
	mu           sync.Mutex
	maxMessages  int
	lookbackDays int
}

// NewExtractor creates a new Slack extractor with the given bot token.
func NewExtractor(token string, maxMessages, lookbackDays int) *Extractor {
	return &Extractor{
		client:       NewClient(token),
		userCache:    make(map[string]string),
		maxMessages:  maxMessages,
		lookbackDays: lookbackDays,
	}
}

// GetInfo fetches metadata about a Slack channel.
func (e *Extractor) GetInfo(ctx context.Context, channelID string) (*ChannelInfo, error) {
	return e.client.GetChannelInfo(ctx, channelID)
}

// Extract fetches messages from a Slack channel and writes them as text to outputPath.
func (e *Extractor) Extract(ctx context.Context, channelID, outputPath string, opts ExtractOptions) (*ExtractionResult, error) {
	// Fetch channel info
	info, err := e.client.GetChannelInfo(ctx, channelID)
	if err != nil {
		return &ExtractionResult{
			Status:    "error",
			Method:    "slack_api",
			ChannelID: channelID,
			Error:     fmt.Sprintf("failed to get channel info: %v", err),
			ErrorType: "channel_not_found",
		}, fmt.Errorf("failed to get channel info: %w", err)
	}

	// If no date range specified, probe volume to decide whether to limit
	if opts.Since.IsZero() && opts.Until.IsZero() {
		_, hasMore, err := e.client.ProbeVolume(ctx, channelID, e.maxMessages)
		if err == nil && hasMore {
			// High-volume channel — apply lookback
			opts.Since = time.Now().AddDate(0, 0, -e.lookbackDays)
		}
		// Otherwise fetch everything
	}

	// Fetch message history
	messages, err := e.client.GetHistory(ctx, channelID, opts.Since, opts.Until)
	if err != nil {
		return &ExtractionResult{
			Status:      "error",
			Method:      "slack_api",
			ChannelID:   channelID,
			ChannelName: info.Name,
			Error:       fmt.Sprintf("failed to fetch history: %v", err),
			ErrorType:   "fetch_failed",
		}, fmt.Errorf("failed to fetch channel history: %w", err)
	}

	// Sort messages chronologically (Slack returns newest first)
	sort.Slice(messages, func(i, j int) bool {
		return messages[i].Timestamp < messages[j].Timestamp
	})

	// Filter out subtypes (joins, leaves, etc.) — keep only real messages
	var realMessages []Message
	for _, msg := range messages {
		if msg.SubType == "" || msg.SubType == "file_share" || msg.SubType == "me_message" {
			realMessages = append(realMessages, msg)
		}
	}

	// Render messages to text
	var buf strings.Builder
	threadCount := 0

	// Write header
	fmt.Fprintf(&buf, "# Slack Channel: #%s\n", info.Name)
	if info.Topic != "" {
		fmt.Fprintf(&buf, "# Topic: %s\n", info.Topic)
	}
	if !opts.Since.IsZero() || !opts.Until.IsZero() {
		fmt.Fprintf(&buf, "# Date range: %s to %s\n",
			formatDateOrOpen(opts.Since, "beginning"),
			formatDateOrOpen(opts.Until, "now"))
	}
	fmt.Fprintf(&buf, "# Messages: %d\n\n", len(realMessages))

	for _, msg := range realMessages {
		userName := e.resolveUser(ctx, msg.User)
		ts := parseSlackTimestamp(msg.Timestamp)
		permalink := buildPermalink(info.Name, channelID, msg.Timestamp)

		fmt.Fprintf(&buf, "[%s] @%s (%s):\n%s\n\n",
			ts.Format("2006-01-02 15:04"),
			userName,
			permalink,
			e.cleanSlackMarkup(ctx, msg.Text),
		)

		// Fetch thread replies if this message has them
		if opts.IncludeThreads && msg.ReplyCount > 0 {
			replies, err := e.client.GetThreadReplies(ctx, channelID, msg.Timestamp)
			if err != nil {
				// Log but continue — don't fail the whole extraction for one thread
				fmt.Fprintf(&buf, "  [thread: failed to fetch %d replies]\n\n", msg.ReplyCount)
				continue
			}

			threadCount++
			for _, reply := range replies {
				replyUser := e.resolveUser(ctx, reply.User)
				replyTS := parseSlackTimestamp(reply.Timestamp)
				replyPermalink := buildThreadPermalink(info.Name, channelID, reply.Timestamp, msg.Timestamp)
				cleanText := e.cleanSlackMarkup(ctx, reply.Text)

				fmt.Fprintf(&buf, "  [thread reply %s] @%s (%s):\n  %s\n\n",
					replyTS.Format("2006-01-02 15:04"),
					replyUser,
					replyPermalink,
					strings.ReplaceAll(cleanText, "\n", "\n  "),
				)
			}
		}
	}

	text := buf.String()

	// Ensure output directory exists
	if err := os.MkdirAll(filepath.Dir(outputPath), 0755); err != nil {
		return &ExtractionResult{
			Status:      "error",
			Method:      "slack_api",
			ChannelID:   channelID,
			ChannelName: info.Name,
			Error:       fmt.Sprintf("failed to create output directory: %v", err),
			ErrorType:   "io_error",
		}, fmt.Errorf("failed to create output directory: %w", err)
	}

	if err := os.WriteFile(outputPath, []byte(text), 0644); err != nil {
		return &ExtractionResult{
			Status:      "error",
			Method:      "slack_api",
			ChannelID:   channelID,
			ChannelName: info.Name,
			Error:       fmt.Sprintf("failed to write output file: %v", err),
			ErrorType:   "io_error",
		}, fmt.Errorf("failed to write output file: %w", err)
	}

	absOutputPath, _ := filepath.Abs(outputPath)

	return &ExtractionResult{
		Status:       "success",
		Method:       "slack_api",
		ChannelID:    channelID,
		ChannelName:  info.Name,
		MessageCount: len(realMessages),
		ThreadCount:  threadCount,
		TotalChars:   len(text),
		OutputFile:   absOutputPath,
	}, nil
}

// ExtractToSessionDir extracts Slack channel text and saves it to the session's text directory.
func (e *Extractor) ExtractToSessionDir(ctx context.Context, channelID, sessionDir, docName string, opts ExtractOptions) (*ExtractionResult, error) {
	textDir := filepath.Join(sessionDir, "text")
	outputPath := filepath.Join(textDir, docName+".txt")
	return e.Extract(ctx, channelID, outputPath, opts)
}

// Slack markup patterns
var (
	// <@U123ABC> user mentions
	slackUserMentionRe = regexp.MustCompile(`<@(U[A-Z0-9]+)>`)
	// <#C123ABC|channel-name> channel references
	slackChannelRefRe = regexp.MustCompile(`<#[A-Z0-9]+\|([^>]+)>`)
	// <#C123ABC> channel references without label
	slackChannelRefBareRe = regexp.MustCompile(`<#([A-Z0-9]+)>`)
	// <https://url|label> links with display text
	slackLinkLabelRe = regexp.MustCompile(`<(https?://[^|>]+)\|([^>]+)>`)
	// <https://url> bare links
	slackLinkBareRe = regexp.MustCompile(`<(https?://[^>]+)>`)
)

// cleanSlackMarkup converts Slack mrkdwn to plain readable text.
// Keeps emoji shortcodes (e.g. :wave:) intact since they carry meaning.
func (e *Extractor) cleanSlackMarkup(ctx context.Context, text string) string {
	// Resolve user mentions: <@U123> → @displayname
	text = slackUserMentionRe.ReplaceAllStringFunc(text, func(match string) string {
		userID := slackUserMentionRe.FindStringSubmatch(match)[1]
		name := e.resolveUser(ctx, userID)
		return "@" + name
	})

	// Channel references: <#C123|channel-name> → #channel-name
	text = slackChannelRefRe.ReplaceAllString(text, "#$1")
	text = slackChannelRefBareRe.ReplaceAllString(text, "#$1")

	// Links with labels: <https://example.com|Example> → Example (https://example.com)
	text = slackLinkLabelRe.ReplaceAllString(text, "$2 ($1)")

	// Bare links: <https://example.com> → https://example.com
	text = slackLinkBareRe.ReplaceAllString(text, "$1")

	// HTML entities
	text = strings.ReplaceAll(text, "&amp;", "&")
	text = strings.ReplaceAll(text, "&lt;", "<")
	text = strings.ReplaceAll(text, "&gt;", ">")

	return text
}

// resolveUser looks up a user's display name, caching results.
func (e *Extractor) resolveUser(ctx context.Context, userID string) string {
	if userID == "" {
		return "unknown"
	}

	e.mu.Lock()
	if name, ok := e.userCache[userID]; ok {
		e.mu.Unlock()
		return name
	}
	e.mu.Unlock()

	user, err := e.client.GetUserInfo(ctx, userID)
	if err != nil {
		return userID // Fall back to raw ID
	}

	e.mu.Lock()
	e.userCache[userID] = user.DisplayName
	e.mu.Unlock()

	return user.DisplayName
}

// parseSlackTimestamp converts a Slack timestamp (e.g., "1234567890.123456") to time.Time.
func parseSlackTimestamp(ts string) time.Time {
	parts := strings.SplitN(ts, ".", 2)
	if len(parts) == 0 {
		return time.Time{}
	}
	var sec int64
	for _, c := range parts[0] {
		sec = sec*10 + int64(c-'0')
	}
	return time.Unix(sec, 0)
}

// buildPermalink builds a Slack message permalink.
func buildPermalink(channelName, channelID, messageTS string) string {
	// Slack permalinks use the timestamp without the dot
	tsNoDot := strings.ReplaceAll(messageTS, ".", "")
	return fmt.Sprintf("https://slack.com/archives/%s/p%s", channelID, tsNoDot)
}

// buildThreadPermalink builds a Slack thread reply permalink.
func buildThreadPermalink(channelName, channelID, replyTS, threadTS string) string {
	tsNoDot := strings.ReplaceAll(replyTS, ".", "")
	return fmt.Sprintf("https://slack.com/archives/%s/p%s?thread_ts=%s&cid=%s",
		channelID, tsNoDot, threadTS, channelID)
}

// formatDateOrOpen formats a time, returning fallback if zero.
func formatDateOrOpen(t time.Time, fallback string) string {
	if t.IsZero() {
		return fallback
	}
	return t.Format("2006-01-02")
}
