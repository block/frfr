package models

import (
	"strings"
	"time"
)

// FlexibleTime is a time.Time that can parse multiple formats (with/without timezone)
type FlexibleTime struct {
	time.Time
}

// UnmarshalJSON handles both RFC3339 (Go) and Python ISO format timestamps
func (ft *FlexibleTime) UnmarshalJSON(data []byte) error {
	s := strings.Trim(string(data), "\"")
	if s == "" || s == "null" {
		return nil
	}

	// Try RFC3339 first (Go's default with timezone)
	t, err := time.Parse(time.RFC3339, s)
	if err == nil {
		ft.Time = t
		return nil
	}

	// Try RFC3339Nano
	t, err = time.Parse(time.RFC3339Nano, s)
	if err == nil {
		ft.Time = t
		return nil
	}

	// Try Python's ISO format without timezone
	t, err = time.Parse("2006-01-02T15:04:05.999999", s)
	if err == nil {
		ft.Time = t
		return nil
	}

	// Try without microseconds
	t, err = time.Parse("2006-01-02T15:04:05", s)
	if err == nil {
		ft.Time = t
		return nil
	}

	return err
}

// MarshalJSON outputs RFC3339 format
func (ft FlexibleTime) MarshalJSON() ([]byte, error) {
	if ft.Time.IsZero() {
		return []byte("null"), nil
	}
	return []byte("\"" + ft.Time.Format(time.RFC3339) + "\""), nil
}

// SessionStatus represents the overall status of a session
type SessionStatus string

const (
	SessionStatusActive     SessionStatus = "active"
	SessionStatusProcessing SessionStatus = "processing"
	SessionStatusCompleted  SessionStatus = "completed"
)

// NameHistoryEntry tracks session name changes
type NameHistoryEntry struct {
	Name         string       `json:"name"`
	Timestamp    FlexibleTime `json:"timestamp"`
	Reason       string       `json:"reason"`
	PreviousName string       `json:"previous_name,omitempty"`
}

// Session represents a frfr session with documents and facts
type Session struct {
	SessionID        string                  `json:"session_id"`
	CreatedAt        FlexibleTime            `json:"created_at"`
	Status           SessionStatus           `json:"status"`
	DocumentRegistry map[string]DocumentInfo `json:"document_registry"`
	NameHistory      []NameHistoryEntry      `json:"name_history"`
}

// NewSession creates a new session with the given ID
func NewSession(sessionID string) *Session {
	now := FlexibleTime{time.Now()}
	return &Session{
		SessionID:        sessionID,
		CreatedAt:        now,
		Status:           SessionStatusActive,
		DocumentRegistry: make(map[string]DocumentInfo),
		NameHistory: []NameHistoryEntry{{
			Name:      sessionID,
			Timestamp: now,
			Reason:    "Initial creation",
		}},
	}
}

// GetDocumentCount returns the number of documents in the session
func (s *Session) GetDocumentCount() int {
	return len(s.DocumentRegistry)
}

// GetName returns the current session name (last in history)
func (s *Session) GetName() string {
	if len(s.NameHistory) > 0 {
		return s.NameHistory[len(s.NameHistory)-1].Name
	}
	return s.SessionID
}

// AddNameHistory records a name change
func (s *Session) AddNameHistory(newName, reason string) {
	previousName := s.GetName()
	s.NameHistory = append(s.NameHistory, NameHistoryEntry{
		Name:         newName,
		Timestamp:    FlexibleTime{time.Now()},
		Reason:       reason,
		PreviousName: previousName,
	})
}

// SessionListItem is a summary view of a session for list display
type SessionListItem struct {
	SessionID     string        `json:"session_id"`
	Name          string        `json:"name"`
	CreatedAt     FlexibleTime  `json:"created_at"`
	Status        SessionStatus `json:"status"`
	DocumentCount int           `json:"document_count"`
	FactCount     int           `json:"fact_count"`
}

// QueryHistoryEntry represents a past query and its result
type QueryHistoryEntry struct {
	Query     string    `json:"query"`
	Answer    string    `json:"answer"`
	Timestamp time.Time `json:"timestamp"`
	Sources   []string  `json:"sources,omitempty"`
}

// ProcessingEvent represents a real-time processing update
type ProcessingEvent struct {
	Type      string      `json:"type"` // chunk_start, chunk_complete, fact_extracted, error, complete
	Timestamp time.Time   `json:"timestamp"`
	Document  string      `json:"document,omitempty"`
	ChunkID   string      `json:"chunk_id,omitempty"`
	Message   string      `json:"message,omitempty"`
	Progress  float64     `json:"progress,omitempty"` // 0.0 - 1.0
	Data      interface{} `json:"data,omitempty"`
}

// Processing event type constants
const (
	EventTypeChunkStart    = "chunk_start"
	EventTypeChunkComplete = "chunk_complete"
	EventTypeFactExtracted = "fact_extracted"
	EventTypeError         = "error"
	EventTypeComplete      = "complete"
	EventTypeDocStart      = "document_start"
	EventTypeDocComplete   = "document_complete"
	EventTypeSummaryStart  = "summary_start"
	EventTypeSummaryDone   = "summary_complete"
	EventTypeInfo          = "info"
)
