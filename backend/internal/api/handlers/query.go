package handlers

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"github.com/nesposito/frfr/internal/config"
	"github.com/nesposito/frfr/internal/domain/models"
	"github.com/nesposito/frfr/internal/services/claude"
	"github.com/nesposito/frfr/internal/services/query"
	"github.com/nesposito/frfr/internal/services/session"
)

// QueryHandler handles query-related API requests
type QueryHandler struct {
	store   *session.Store
	config  *config.Config
	history map[string][]models.QueryHistoryEntry // sessionID -> history
}

// NewQueryHandler creates a new query handler
func NewQueryHandler(store *session.Store, cfg *config.Config) *QueryHandler {
	return &QueryHandler{
		store:   store,
		config:  cfg,
		history: make(map[string][]models.QueryHistoryEntry),
	}
}

// QueryRequest is the request body for submitting a query
type QueryRequest struct {
	Query     string `json:"query"`
	MaxPasses int    `json:"max_passes,omitempty"` // For multi-pass query
}

// QueryResponse is the response for a query
type QueryResponse struct {
	Query    string           `json:"query"`
	Answer   string           `json:"answer"`
	Sources  []SourceEvidence `json:"sources"`
	Duration string           `json:"duration"`
}

// SourceEvidence contains evidence for a query answer
type SourceEvidence struct {
	Claim      string  `json:"claim"`
	Quote      string  `json:"quote"`
	Document   string  `json:"document"`
	Location   string  `json:"location"`
	Confidence float64 `json:"confidence"`
	ChunkText  string  `json:"chunk_text,omitempty"`
	Highlights []int   `json:"highlights,omitempty"` // [start, end] pairs
}

// Submit handles a query submission
func (h *QueryHandler) Submit(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("id")
	if sessionID == "" {
		writeError(w, http.StatusBadRequest, "Session ID is required")
		return
	}

	var req QueryRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid request body: "+err.Error())
		return
	}

	if req.Query == "" {
		writeError(w, http.StatusBadRequest, "Query is required")
		return
	}

	// Check session exists
	if _, err := h.store.Get(sessionID); err != nil {
		if strings.Contains(err.Error(), "not found") {
			writeError(w, http.StatusNotFound, err.Error())
		} else {
			writeError(w, http.StatusInternalServerError, "Failed to get session: "+err.Error())
		}
		return
	}

	start := time.Now()

	// Load facts for the session
	facts, err := h.store.LoadAllFacts(sessionID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Failed to load facts: "+err.Error())
		return
	}

	// Create Claude client and query processor
	claudeClient := claude.NewClient(h.config.AnthropicAPIKey)
	sessionDir := h.store.GetSessionDir(sessionID)
	chunkManager := query.NewChunkManager(sessionDir)
	chunkManager.LoadChunks() // Load chunks for context retrieval
	processor := query.NewProcessor(claudeClient, chunkManager, facts)

	// Process query with Claude
	ctx := context.Background()
	maxPasses := req.MaxPasses
	if maxPasses <= 0 {
		maxPasses = 1
	}

	result, err := processor.MultiPassQuery(ctx, req.Query, maxPasses)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Query processing failed: "+err.Error())
		return
	}

	// Convert to response format
	var sources []SourceEvidence
	for _, src := range result.Sources {
		source := SourceEvidence{
			Claim:      src.Claim,
			Quote:      src.Quote,
			Document:   src.Document,
			Location:   src.Location,
			Confidence: src.Confidence,
			ChunkText:  src.ChunkText,
		}

		// Find quote position and trim context around it
		if source.ChunkText != "" && source.Quote != "" {
			// Try exact match first
			idx := strings.Index(source.ChunkText, source.Quote)
			quoteLen := len(source.Quote)

			// If not found, try matching with normalized whitespace
			if idx < 0 {
				idx, quoteLen = findQuoteWithNormalizedWhitespace(source.ChunkText, source.Quote)
			}

			if idx >= 0 {
				// Trim to ~500 chars of context around the quote
				contextChars := 250
				start := idx - contextChars
				if start < 0 {
					start = 0
				}
				end := idx + quoteLen + contextChars
				if end > len(source.ChunkText) {
					end = len(source.ChunkText)
				}

				// Adjust to not cut words
				if start > 0 {
					// Find next space after start
					for start < idx && source.ChunkText[start] != ' ' && source.ChunkText[start] != '\n' {
						start++
					}
					start++ // skip the space
				}
				if end < len(source.ChunkText) {
					// Find previous space before end
					for end > idx+quoteLen && source.ChunkText[end-1] != ' ' && source.ChunkText[end-1] != '\n' {
						end--
					}
				}

				// Update chunk text and highlight positions
				source.ChunkText = source.ChunkText[start:end]
				newIdx := idx - start
				source.Highlights = []int{newIdx, newIdx + quoteLen}
			} else {
				// Quote not found - just show first ~500 chars
				if len(source.ChunkText) > 500 {
					source.ChunkText = source.ChunkText[:500] + "..."
				}
			}
		}

		sources = append(sources, source)
	}

	answer := result.Answer

	duration := time.Since(start)

	// Store in history
	historyEntry := models.QueryHistoryEntry{
		Query:     req.Query,
		Answer:    answer,
		Timestamp: time.Now(),
	}
	for _, s := range sources {
		historyEntry.Sources = append(historyEntry.Sources, s.Document+":"+s.Location)
	}
	h.history[sessionID] = append(h.history[sessionID], historyEntry)

	writeJSON(w, http.StatusOK, QueryResponse{
		Query:    req.Query,
		Answer:   answer,
		Sources:  sources,
		Duration: duration.String(),
	})
}

// History returns query history for a session
func (h *QueryHandler) History(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("id")
	if sessionID == "" {
		writeError(w, http.StatusBadRequest, "Session ID is required")
		return
	}

	// Check session exists
	if _, err := h.store.Get(sessionID); err != nil {
		if strings.Contains(err.Error(), "not found") {
			writeError(w, http.StatusNotFound, err.Error())
		} else {
			writeError(w, http.StatusInternalServerError, "Failed to get session: "+err.Error())
		}
		return
	}

	history := h.history[sessionID]
	if history == nil {
		history = []models.QueryHistoryEntry{}
	}

	writeJSON(w, http.StatusOK, history)
}

// findQuoteWithNormalizedWhitespace finds a quote in text by normalizing whitespace.
// Returns the start index in the original text and the length of the matched span,
// or (-1, 0) if not found.
func findQuoteWithNormalizedWhitespace(text, quote string) (int, int) {
	// Normalize quote: collapse whitespace to single space
	normalizedQuote := normalizeWhitespace(quote)
	if normalizedQuote == "" {
		return -1, 0
	}

	// Build a normalized version of text and track original positions
	textRunes := []rune(text)
	var normalizedText strings.Builder
	posMap := make([]int, 0, len(textRunes)) // maps normalized index to original index

	inWhitespace := false
	for i, r := range textRunes {
		if r == ' ' || r == '\n' || r == '\r' || r == '\t' {
			if !inWhitespace {
				normalizedText.WriteRune(' ')
				posMap = append(posMap, i)
				inWhitespace = true
			}
		} else {
			normalizedText.WriteRune(r)
			posMap = append(posMap, i)
			inWhitespace = false
		}
	}

	normalized := normalizedText.String()
	idx := strings.Index(normalized, normalizedQuote)
	if idx < 0 {
		return -1, 0
	}

	// Map back to original position
	if idx >= len(posMap) {
		return -1, 0
	}
	origStart := posMap[idx]

	// Find end position
	endIdx := idx + len(normalizedQuote)
	var origEnd int
	if endIdx >= len(posMap) {
		origEnd = len(text)
	} else {
		origEnd = posMap[endIdx]
	}

	return origStart, origEnd - origStart
}

// normalizeWhitespace collapses all whitespace to single spaces
func normalizeWhitespace(s string) string {
	var result strings.Builder
	inWhitespace := false
	for _, r := range s {
		if r == ' ' || r == '\n' || r == '\r' || r == '\t' {
			if !inWhitespace {
				result.WriteRune(' ')
				inWhitespace = true
			}
		} else {
			result.WriteRune(r)
			inWhitespace = false
		}
	}
	return strings.TrimSpace(result.String())
}
