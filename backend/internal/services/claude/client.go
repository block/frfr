package claude

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os/exec"
	"strings"
	"time"
)

const (
	anthropicAPIURL  = "https://api.anthropic.com/v1/messages"
	anthropicVersion = "2023-06-01"
	defaultModel     = "claude-opus-4-6"
	defaultMaxTokens = 4096
	defaultTimeout   = 10 * time.Minute
)

// Client handles communication with the Anthropic Claude API
type Client struct {
	apiKey     string
	httpClient *http.Client
	model      string
	timeout    time.Duration
	useNative  bool // Use native credentials (claude CLI) when no API key
	fastMode   bool // Fast mode: same model, faster output via API speed parameter
}

// NewClient creates a new Claude API client.
// If apiKey is empty, the client will attempt to use native credentials via the claude CLI.
func NewClient(apiKey string) *Client {
	return &Client{
		apiKey: apiKey,
		httpClient: &http.Client{
			Timeout: defaultTimeout,
		},
		model:     defaultModel,
		timeout:   defaultTimeout,
		useNative: apiKey == "",
	}
}

// WithModel sets the model to use
func (c *Client) WithModel(model string) *Client {
	c.model = model
	return c
}

// WithFastMode enables fast mode (same model, faster output via API speed parameter)
func (c *Client) WithFastMode(fast bool) *Client {
	c.fastMode = fast
	return c
}

// WithTimeout sets the request timeout
func (c *Client) WithTimeout(timeout time.Duration) *Client {
	c.timeout = timeout
	c.httpClient.Timeout = timeout
	return c
}

// MessageRequest represents a request to the Messages API
type MessageRequest struct {
	Model     string    `json:"model"`
	MaxTokens int       `json:"max_tokens"`
	Speed     string    `json:"speed,omitempty"`
	System    string    `json:"system,omitempty"`
	Messages  []Message `json:"messages"`
}

// Message represents a single message in a conversation
type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// MessageResponse represents a response from the Messages API
type MessageResponse struct {
	ID           string         `json:"id"`
	Type         string         `json:"type"`
	Role         string         `json:"role"`
	Content      []ContentBlock `json:"content"`
	Model        string         `json:"model"`
	StopReason   string         `json:"stop_reason"`
	StopSequence *string        `json:"stop_sequence,omitempty"`
	Usage        Usage          `json:"usage"`
}

// ContentBlock represents a block of content in a message
type ContentBlock struct {
	Type string `json:"type"`
	Text string `json:"text,omitempty"`
}

// Usage contains token usage information
type Usage struct {
	InputTokens  int `json:"input_tokens"`
	OutputTokens int `json:"output_tokens"`
}

// APIError represents an error from the Anthropic API
type APIError struct {
	Type    string `json:"type"`
	Message string `json:"message"`
}

func (e *APIError) Error() string {
	return fmt.Sprintf("API error (%s): %s", e.Type, e.Message)
}

// ErrorResponse represents an error response from the API
type ErrorResponse struct {
	Type  string   `json:"type"`
	Error APIError `json:"error"`
}

// PromptOptions contains options for a prompt request
type PromptOptions struct {
	SystemPrompt string
	MaxTokens    int
	Model        string
}

// Prompt sends a prompt to the Claude API and returns the response text
func (c *Client) Prompt(ctx context.Context, prompt string, opts *PromptOptions) (string, error) {
	if opts == nil {
		opts = &PromptOptions{}
	}

	maxTokens := opts.MaxTokens
	if maxTokens == 0 {
		maxTokens = defaultMaxTokens
	}

	model := opts.Model
	if model == "" {
		model = c.model
	}

	req := MessageRequest{
		Model:     model,
		MaxTokens: maxTokens,
		System:    opts.SystemPrompt,
		Messages: []Message{
			{Role: "user", Content: prompt},
		},
	}
	if c.fastMode {
		req.Speed = "fast"
	}

	resp, err := c.sendRequest(ctx, req)
	if err != nil {
		return "", err
	}

	// Extract text from response
	var text string
	for _, block := range resp.Content {
		if block.Type == "text" {
			text += block.Text
		}
	}

	return text, nil
}

// PromptWithUsage sends a prompt and returns both the response and usage info
func (c *Client) PromptWithUsage(ctx context.Context, prompt string, opts *PromptOptions) (string, *Usage, error) {
	if opts == nil {
		opts = &PromptOptions{}
	}

	maxTokens := opts.MaxTokens
	if maxTokens == 0 {
		maxTokens = defaultMaxTokens
	}

	model := opts.Model
	if model == "" {
		model = c.model
	}

	req := MessageRequest{
		Model:     model,
		MaxTokens: maxTokens,
		System:    opts.SystemPrompt,
		Messages: []Message{
			{Role: "user", Content: prompt},
		},
	}
	if c.fastMode {
		req.Speed = "fast"
	}

	resp, err := c.sendRequest(ctx, req)
	if err != nil {
		return "", nil, err
	}

	// Extract text from response
	var text string
	for _, block := range resp.Content {
		if block.Type == "text" {
			text += block.Text
		}
	}

	return text, &resp.Usage, nil
}

// sendRequest sends a request to the Anthropic API
func (c *Client) sendRequest(ctx context.Context, req MessageRequest) (*MessageResponse, error) {
	// Use native credentials via CLI if no API key provided
	if c.useNative {
		return c.sendRequestViaCLI(ctx, req)
	}

	return c.sendRequestViaHTTP(ctx, req)
}

// sendRequestViaHTTP sends a request directly to the Anthropic HTTP API
func (c *Client) sendRequestViaHTTP(ctx context.Context, req MessageRequest) (*MessageResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", anthropicAPIURL, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("x-api-key", c.apiKey)
	httpReq.Header.Set("anthropic-version", anthropicVersion)
	if c.fastMode {
		httpReq.Header.Set("anthropic-beta", "fast-mode-2026-02-01")
	}

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		var errResp ErrorResponse
		if err := json.Unmarshal(respBody, &errResp); err == nil {
			return nil, &errResp.Error
		}
		return nil, fmt.Errorf("API request failed with status %d: %s", resp.StatusCode, string(respBody))
	}

	var msgResp MessageResponse
	if err := json.Unmarshal(respBody, &msgResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	return &msgResp, nil
}

// sendRequestViaCLI sends a request using the claude CLI (uses native credentials)
func (c *Client) sendRequestViaCLI(ctx context.Context, req MessageRequest) (*MessageResponse, error) {
	// Build the prompt from messages
	var prompt strings.Builder
	if req.System != "" {
		prompt.WriteString("System: ")
		prompt.WriteString(req.System)
		prompt.WriteString("\n\n")
	}
	for _, msg := range req.Messages {
		prompt.WriteString(msg.Content)
	}

	// Use claude CLI with --print flag for non-interactive output
	cmd := exec.CommandContext(ctx, "claude", "--print", "--model", req.Model, prompt.String())

	output, err := cmd.Output()
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			return nil, fmt.Errorf("claude CLI failed: %s", string(exitErr.Stderr))
		}
		return nil, fmt.Errorf("failed to run claude CLI (is it installed?): %w", err)
	}

	// Wrap CLI output in a MessageResponse
	return &MessageResponse{
		ID:         "cli-response",
		Type:       "message",
		Role:       "assistant",
		Model:      req.Model,
		StopReason: "end_turn",
		Content: []ContentBlock{
			{Type: "text", Text: strings.TrimSpace(string(output))},
		},
		Usage: Usage{
			InputTokens:  0, // CLI doesn't report usage
			OutputTokens: 0,
		},
	}, nil
}
