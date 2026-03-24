package slack

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

// Client is a thin Slack Web API client.
type Client struct {
	token      string
	httpClient *http.Client
}

// NewClient creates a new Slack API client with the given bot token.
func NewClient(token string) *Client {
	return &Client{
		token: token,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// Message represents a Slack message.
type Message struct {
	User      string    `json:"user"`
	Text      string    `json:"text"`
	Timestamp string    `json:"ts"`
	ThreadTS  string    `json:"thread_ts,omitempty"`
	ReplyCount int      `json:"reply_count,omitempty"`
	SubType   string    `json:"subtype,omitempty"`
}

// User represents a Slack user profile.
type User struct {
	ID          string `json:"id"`
	DisplayName string `json:"display_name"`
	RealName    string `json:"real_name"`
}

// ChannelInfo represents basic Slack channel metadata.
type ChannelInfo struct {
	ID           string `json:"id"`
	Name         string `json:"name"`
	Topic        string `json:"topic"`
	Purpose      string `json:"purpose"`
	MemberCount  int    `json:"num_members"`
}

// conversationsHistoryResponse is the Slack API response for conversations.history.
type conversationsHistoryResponse struct {
	OK               bool      `json:"ok"`
	Error            string    `json:"error,omitempty"`
	Messages         []Message `json:"messages"`
	HasMore          bool      `json:"has_more"`
	ResponseMetadata struct {
		NextCursor string `json:"next_cursor"`
	} `json:"response_metadata"`
}

// conversationsRepliesResponse is the Slack API response for conversations.replies.
type conversationsRepliesResponse struct {
	OK               bool      `json:"ok"`
	Error            string    `json:"error,omitempty"`
	Messages         []Message `json:"messages"`
	HasMore          bool      `json:"has_more"`
	ResponseMetadata struct {
		NextCursor string `json:"next_cursor"`
	} `json:"response_metadata"`
}

// conversationsInfoResponse is the Slack API response for conversations.info.
type conversationsInfoResponse struct {
	OK      bool `json:"ok"`
	Error   string `json:"error,omitempty"`
	Channel struct {
		ID      string `json:"id"`
		Name    string `json:"name"`
		Topic   struct {
			Value string `json:"value"`
		} `json:"topic"`
		Purpose struct {
			Value string `json:"value"`
		} `json:"purpose"`
		NumMembers int `json:"num_members"`
	} `json:"channel"`
}

// usersInfoResponse is the Slack API response for users.info.
type usersInfoResponse struct {
	OK    bool   `json:"ok"`
	Error string `json:"error,omitempty"`
	User  struct {
		ID      string `json:"id"`
		Profile struct {
			DisplayName string `json:"display_name"`
			RealName    string `json:"real_name"`
		} `json:"profile"`
	} `json:"user"`
}

// GetChannelInfo fetches metadata about a channel.
func (c *Client) GetChannelInfo(ctx context.Context, channelID string) (*ChannelInfo, error) {
	params := url.Values{"channel": {channelID}}
	body, err := c.apiGet(ctx, "conversations.info", params)
	if err != nil {
		return nil, err
	}

	var resp conversationsInfoResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("failed to parse conversations.info response: %w", err)
	}
	if !resp.OK {
		return nil, fmt.Errorf("slack API error: %s", resp.Error)
	}

	return &ChannelInfo{
		ID:          resp.Channel.ID,
		Name:        resp.Channel.Name,
		Topic:       resp.Channel.Topic.Value,
		Purpose:     resp.Channel.Purpose.Value,
		MemberCount: resp.Channel.NumMembers,
	}, nil
}

// ProbeVolume fetches a single page of history to check if the channel has more
// than `limit` messages. Returns (messageCount, hasMore, error).
func (c *Client) ProbeVolume(ctx context.Context, channelID string, limit int) (int, bool, error) {
	params := url.Values{
		"channel": {channelID},
		"limit":   {fmt.Sprintf("%d", limit)},
	}

	body, err := c.apiGet(ctx, "conversations.history", params)
	if err != nil {
		return 0, false, err
	}

	var resp conversationsHistoryResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return 0, false, fmt.Errorf("failed to parse response: %w", err)
	}
	if !resp.OK {
		return 0, false, fmt.Errorf("slack API error: %s", resp.Error)
	}

	return len(resp.Messages), resp.HasMore, nil
}

// GetHistory fetches channel message history with pagination.
// If since is non-zero, only messages after that time are returned.
func (c *Client) GetHistory(ctx context.Context, channelID string, since, until time.Time) ([]Message, error) {
	var allMessages []Message
	cursor := ""

	for {
		params := url.Values{
			"channel": {channelID},
			"limit":   {"200"},
		}
		if !since.IsZero() {
			params.Set("oldest", fmt.Sprintf("%d.000000", since.Unix()))
		}
		if !until.IsZero() {
			params.Set("latest", fmt.Sprintf("%d.000000", until.Unix()))
		}
		if cursor != "" {
			params.Set("cursor", cursor)
		}

		body, err := c.apiGet(ctx, "conversations.history", params)
		if err != nil {
			return nil, err
		}

		var resp conversationsHistoryResponse
		if err := json.Unmarshal(body, &resp); err != nil {
			return nil, fmt.Errorf("failed to parse conversations.history response: %w", err)
		}
		if !resp.OK {
			return nil, fmt.Errorf("slack API error: %s", resp.Error)
		}

		allMessages = append(allMessages, resp.Messages...)

		if !resp.HasMore || resp.ResponseMetadata.NextCursor == "" {
			break
		}
		cursor = resp.ResponseMetadata.NextCursor
	}

	return allMessages, nil
}

// GetThreadReplies fetches all replies in a thread.
func (c *Client) GetThreadReplies(ctx context.Context, channelID, threadTS string) ([]Message, error) {
	var allReplies []Message
	cursor := ""

	for {
		params := url.Values{
			"channel": {channelID},
			"ts":      {threadTS},
			"limit":   {"200"},
		}
		if cursor != "" {
			params.Set("cursor", cursor)
		}

		body, err := c.apiGet(ctx, "conversations.replies", params)
		if err != nil {
			return nil, err
		}

		var resp conversationsRepliesResponse
		if err := json.Unmarshal(body, &resp); err != nil {
			return nil, fmt.Errorf("failed to parse conversations.replies response: %w", err)
		}
		if !resp.OK {
			return nil, fmt.Errorf("slack API error: %s", resp.Error)
		}

		// Skip the first message (parent) — it's already in history
		for _, msg := range resp.Messages {
			if msg.Timestamp != threadTS {
				allReplies = append(allReplies, msg)
			}
		}

		if !resp.HasMore || resp.ResponseMetadata.NextCursor == "" {
			break
		}
		cursor = resp.ResponseMetadata.NextCursor
	}

	return allReplies, nil
}

// GetUserInfo fetches a user's profile.
func (c *Client) GetUserInfo(ctx context.Context, userID string) (*User, error) {
	params := url.Values{"user": {userID}}
	body, err := c.apiGet(ctx, "users.info", params)
	if err != nil {
		return nil, err
	}

	var resp usersInfoResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("failed to parse users.info response: %w", err)
	}
	if !resp.OK {
		return nil, fmt.Errorf("slack API error: %s", resp.Error)
	}

	name := resp.User.Profile.DisplayName
	if name == "" {
		name = resp.User.Profile.RealName
	}

	return &User{
		ID:          resp.User.ID,
		DisplayName: name,
		RealName:    resp.User.Profile.RealName,
	}, nil
}

// apiGet makes an authenticated GET request to a Slack API method.
func (c *Client) apiGet(ctx context.Context, method string, params url.Values) ([]byte, error) {
	u := fmt.Sprintf("https://slack.com/api/%s?%s", method, params.Encode())

	req, err := http.NewRequestWithContext(ctx, "GET", u, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+c.token)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("slack API request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("slack API returned status %d: %s", resp.StatusCode, string(body))
	}

	return body, nil
}
