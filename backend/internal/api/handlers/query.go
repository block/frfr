package handlers

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/nesposito/frfr/internal/config"
	"github.com/nesposito/frfr/internal/domain/models"
	"github.com/nesposito/frfr/internal/services/claude"
	"github.com/nesposito/frfr/internal/services/query"
	"github.com/nesposito/frfr/internal/services/session"
)

func truncateStr(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}

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

				// Trim the chunk text
				source.ChunkText = source.ChunkText[start:end]
				// Convert byte offsets to rune (character) offsets for JavaScript
				// JavaScript slice() works on UTF-16 code units, Go uses bytes
				newIdx := idx - start
				runeStart := len([]rune(source.ChunkText[:newIdx]))
				runeEnd := runeStart + len([]rune(source.ChunkText[newIdx:newIdx+quoteLen]))
				source.Highlights = []int{runeStart, runeEnd}
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

// SubmitStream handles a query submission with SSE progress streaming
func (h *QueryHandler) SubmitStream(w http.ResponseWriter, r *http.Request) {
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

	// Set up SSE headers
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	flusher, ok := w.(http.Flusher)
	if !ok {
		writeError(w, http.StatusInternalServerError, "Streaming not supported")
		return
	}

	// Helper to send SSE events
	sendEvent := func(eventType string, data interface{}) {
		jsonData, _ := json.Marshal(data)
		w.Write([]byte("event: " + eventType + "\n"))
		w.Write([]byte("data: " + string(jsonData) + "\n\n"))
		flusher.Flush()
	}

	start := time.Now()

	// Load facts for the session
	facts, err := h.store.LoadAllFacts(sessionID)
	if err != nil {
		sendEvent("error", map[string]string{"message": "Failed to load facts: " + err.Error()})
		return
	}

	sendEvent("status", map[string]interface{}{
		"message":    "Loaded facts",
		"totalFacts": len(facts),
	})

	// Create Claude client and query processor
	claudeClient := claude.NewClient(h.config.AnthropicAPIKey)
	sessionDir := h.store.GetSessionDir(sessionID)
	chunkManager := query.NewChunkManager(sessionDir)
	chunkManager.LoadChunks()
	processor := query.NewProcessor(claudeClient, chunkManager, facts)

	// Set progress callback to stream batch updates
	processor.SetProgressCallback(func(progress query.BatchProgress) {
		sendEvent("progress", progress)
	})

	// Process query with Claude
	ctx := context.Background()
	maxPasses := req.MaxPasses
	if maxPasses <= 0 {
		maxPasses = 1
	}

	result, err := processor.MultiPassQuery(ctx, req.Query, maxPasses)
	if err != nil {
		sendEvent("error", map[string]string{"message": "Query processing failed: " + err.Error()})
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
			idx := strings.Index(source.ChunkText, source.Quote)
			quoteLen := len(source.Quote)

			if idx < 0 {
				idx, quoteLen = findQuoteWithNormalizedWhitespace(source.ChunkText, source.Quote)
			}

			if idx >= 0 {
				contextChars := 250
				ctxStart := idx - contextChars
				if ctxStart < 0 {
					ctxStart = 0
				}
				end := idx + quoteLen + contextChars
				if end > len(source.ChunkText) {
					end = len(source.ChunkText)
				}

				if ctxStart > 0 {
					for ctxStart < idx && source.ChunkText[ctxStart] != ' ' && source.ChunkText[ctxStart] != '\n' {
						ctxStart++
					}
					ctxStart++
				}
				if end < len(source.ChunkText) {
					for end > idx+quoteLen && source.ChunkText[end-1] != ' ' && source.ChunkText[end-1] != '\n' {
						end--
					}
				}

				// Trim the chunk text
				source.ChunkText = source.ChunkText[ctxStart:end]
				// Convert byte offsets to rune (character) offsets for JavaScript
				// JavaScript slice() works on UTF-16 code units, Go uses bytes
				newIdx := idx - ctxStart
				runeStart := len([]rune(source.ChunkText[:newIdx]))
				runeEnd := runeStart + len([]rune(source.ChunkText[newIdx:newIdx+quoteLen]))
				source.Highlights = []int{runeStart, runeEnd}
			} else {
				// Debug: quote not found - show assigned chunk info
				log.Printf("[DEBUG] Source %d: quote not found. Doc=%s Loc=%s ChunkText len=%d",
					len(sources)+1, source.Document, source.Location, len(source.ChunkText))
				log.Printf("  Quote (first 80): %q", truncateStr(source.Quote, 80))
				log.Printf("  ChunkText (first 80): %q", truncateStr(source.ChunkText, 80))

				if len(source.ChunkText) > 500 {
					source.ChunkText = source.ChunkText[:500] + "..."
				}
			}
		} else if source.ChunkText == "" {
			log.Printf("[DEBUG] Source %d: no chunk text available", len(sources)+1)
		} else if source.Quote == "" {
			log.Printf("[DEBUG] Source %d: no quote available", len(sources)+1)
		}

		sources = append(sources, source)
	}

	duration := time.Since(start)

	// Store in history
	historyEntry := models.QueryHistoryEntry{
		Query:     req.Query,
		Answer:    result.Answer,
		Timestamp: time.Now(),
	}
	for _, s := range sources {
		historyEntry.Sources = append(historyEntry.Sources, s.Document+":"+s.Location)
	}
	h.history[sessionID] = append(h.history[sessionID], historyEntry)

	// Send final result
	sendEvent("result", QueryResponse{
		Query:    req.Query,
		Answer:   result.Answer,
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
// Returns the start BYTE index in the original text and the BYTE length of the matched span,
// or (-1, 0) if not found.
func findQuoteWithNormalizedWhitespace(text, quote string) (int, int) {
	// Normalize quote: collapse whitespace to single space
	normalizedQuote := normalizeWhitespace(quote)
	if normalizedQuote == "" {
		return -1, 0
	}

	// Build a normalized version of text and track original BYTE positions
	// posMap[i] = byte offset in original text for the i-th rune in normalized text
	var normalizedText strings.Builder
	var posMap []int

	inWhitespace := false
	for i, r := range text { // range over string gives byte offset i, rune r
		if r == ' ' || r == '\n' || r == '\r' || r == '\t' {
			if !inWhitespace {
				normalizedText.WriteRune(' ')
				posMap = append(posMap, i) // i is byte offset
				inWhitespace = true
			}
		} else {
			normalizedText.WriteRune(r)
			posMap = append(posMap, i) // i is byte offset
			inWhitespace = false
		}
	}

	normalized := normalizedText.String()

	// Find quote in normalized text - get byte position
	byteIdx := strings.Index(normalized, normalizedQuote)
	if byteIdx < 0 {
		return -1, 0
	}

	// Convert byte index in normalized string to rune index for posMap lookup
	runeIdx := len([]rune(normalized[:byteIdx]))

	// Map back to original byte position
	if runeIdx >= len(posMap) {
		return -1, 0
	}
	origStart := posMap[runeIdx]

	// Find end position - need rune count in the normalized quote
	endRuneIdx := runeIdx + len([]rune(normalizedQuote))
	var origEnd int
	if endRuneIdx >= len(posMap) {
		origEnd = len(text)
	} else {
		origEnd = posMap[endRuneIdx]
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
