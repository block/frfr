package claude

import (
	"bufio"
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

// StreamCallback is called with each chunk of text as it's generated
type StreamCallback func(chunk string)

// PromptStream sends a prompt and streams the response text via callback.
// Returns the full response text when complete.
func (c *Client) PromptStream(ctx context.Context, prompt string, opts *PromptOptions, onChunk StreamCallback) (string, error) {
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

	if c.useNative {
		return c.streamViaCLI(ctx, req, onChunk)
	}
	return c.streamViaHTTP(ctx, req, onChunk)
}

// streamViaCLI streams responses using the claude CLI with stream-json output
func (c *Client) streamViaCLI(ctx context.Context, req MessageRequest, onChunk StreamCallback) (string, error) {
	var prompt strings.Builder
	if req.System != "" {
		prompt.WriteString("System: ")
		prompt.WriteString(req.System)
		prompt.WriteString("\n\n")
	}
	for _, msg := range req.Messages {
		prompt.WriteString(msg.Content)
	}

	args := []string{"--print", "--output-format", "stream-json", "--verbose",
		"--include-partial-messages", "--model", req.Model}
	if req.Speed == "fast" {
		args = append(args, "--settings", `{"fastMode": true}`)
	}
	args = append(args, prompt.String())
	cmd := exec.CommandContext(ctx, "claude", args...)

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return "", fmt.Errorf("failed to create stdout pipe: %w", err)
	}
	cmd.Stderr = nil

	if err := cmd.Start(); err != nil {
		return "", fmt.Errorf("failed to start claude CLI: %w", err)
	}

	var fullText string
	scanner := bufio.NewScanner(stdout)
	scanner.Buffer(make([]byte, 1024*1024), 1024*1024)
	for scanner.Scan() {
		line := scanner.Text()

		// Parse stream-json lines for content_block_delta events
		var event struct {
			Type    string `json:"type"`
			Message struct {
				Content []struct {
					Type string `json:"type"`
					Text string `json:"text"`
				} `json:"content"`
			} `json:"message"`
			Result string `json:"result"`
		}
		if err := json.Unmarshal([]byte(line), &event); err != nil {
			continue
		}

		switch event.Type {
		case "assistant":
			// Partial message - extract new text
			if len(event.Message.Content) > 0 {
				for _, block := range event.Message.Content {
					if block.Type == "text" && len(block.Text) > len(fullText) {
						chunk := block.Text[len(fullText):]
						fullText = block.Text
						if onChunk != nil {
							onChunk(chunk)
						}
					}
				}
			}
		case "result":
			if event.Result != "" && event.Result != fullText {
				if remaining := event.Result[len(fullText):]; remaining != "" {
					if onChunk != nil {
						onChunk(remaining)
					}
				}
				fullText = event.Result
			}
		}
	}

	if err := cmd.Wait(); err != nil {
		if fullText != "" {
			return fullText, nil // Got partial output, return it
		}
		if exitErr, ok := err.(*exec.ExitError); ok {
			return "", fmt.Errorf("claude CLI failed: %s", string(exitErr.Stderr))
		}
		return "", fmt.Errorf("claude CLI failed: %w", err)
	}

	return fullText, nil
}

// streamViaHTTP streams responses using the Anthropic streaming API
func (c *Client) streamViaHTTP(ctx context.Context, req MessageRequest, onChunk StreamCallback) (string, error) {
	// Add stream flag
	type streamRequest struct {
		MessageRequest
		Stream bool `json:"stream"`
	}
	sreq := streamRequest{MessageRequest: req, Stream: true}

	body, err := json.Marshal(sreq)
	if err != nil {
		return "", fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", anthropicAPIURL, bytes.NewReader(body))
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("x-api-key", c.apiKey)
	httpReq.Header.Set("anthropic-version", anthropicVersion)
	if c.fastMode {
		httpReq.Header.Set("anthropic-beta", "fast-mode-2026-02-01")
	}

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return "", fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		var errResp ErrorResponse
		if err := json.Unmarshal(respBody, &errResp); err == nil {
			return "", &errResp.Error
		}
		return "", fmt.Errorf("API request failed with status %d: %s", resp.StatusCode, string(respBody))
	}

	// Parse SSE stream
	var fullText string
	scanner := bufio.NewScanner(resp.Body)
	scanner.Buffer(make([]byte, 1024*1024), 1024*1024)
	for scanner.Scan() {
		line := scanner.Text()
		if !strings.HasPrefix(line, "data: ") {
			continue
		}
		data := line[6:]
		if data == "[DONE]" {
			break
		}

		var event struct {
			Type  string `json:"type"`
			Delta struct {
				Type string `json:"type"`
				Text string `json:"text"`
			} `json:"delta"`
		}
		if err := json.Unmarshal([]byte(data), &event); err != nil {
			continue
		}

		if event.Type == "content_block_delta" && event.Delta.Type == "text_delta" {
			fullText += event.Delta.Text
			if onChunk != nil {
				onChunk(event.Delta.Text)
			}
		}
	}

	return fullText, nil
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
	args := []string{"--print", "--model", req.Model}
	if req.Speed == "fast" {
		args = append(args, "--settings", `{"fastMode": true}`)
	}
	args = append(args, prompt.String())
	cmd := exec.CommandContext(ctx, "claude", args...)

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
