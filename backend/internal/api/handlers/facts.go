package handlers

import (
	"net/http"
	"regexp"
	"strconv"
	"strings"

	"github.com/nesposito/frfr/internal/domain/models"
	"github.com/nesposito/frfr/internal/services/session"
)

// FactsHandler handles facts-related API requests
type FactsHandler struct {
	store *session.Store
}

// NewFactsHandler creates a new facts handler
func NewFactsHandler(store *session.Store) *FactsHandler {
	return &FactsHandler{store: store}
}

// FactsListResponse contains facts with pagination info
type FactsListResponse struct {
	Facts      []models.ExtractedFact `json:"facts"`
	Total      int                    `json:"total"`
	Page       int                    `json:"page"`
	PageSize   int                    `json:"page_size"`
	TotalPages int                    `json:"total_pages"`
}

// FactContextResponse contains a fact with its source context
type FactContextResponse struct {
	Fact       models.ExtractedFact `json:"fact"`
	ChunkText  string               `json:"chunk_text"`
	LineStart  int                  `json:"line_start"`
	LineEnd    int                  `json:"line_end"`
	Highlights []HighlightRange     `json:"highlights"`
}

// HighlightRange indicates text to highlight in the chunk
type HighlightRange struct {
	Start int    `json:"start"`
	End   int    `json:"end"`
	Quote string `json:"quote"`
}

// List returns facts for a session with optional filtering
func (h *FactsHandler) List(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("id")
	if sessionID == "" {
		writeError(w, http.StatusBadRequest, "Session ID is required")
		return
	}

	// Parse query parameters
	query := r.URL.Query()
	search := query.Get("search")
	factType := query.Get("type")
	document := query.Get("document")
	minConfidence := parseFloat(query.Get("min_confidence"), 0)
	page := parseInt(query.Get("page"), 1)
	pageSize := parseInt(query.Get("page_size"), 50)

	// Load all facts
	facts, err := h.store.LoadAllFacts(sessionID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Failed to load facts: "+err.Error())
		return
	}

	// Apply filters
	var filtered []models.ExtractedFact
	for _, fact := range facts {
		// Filter by document
		if document != "" && fact.SourceDoc != document {
			continue
		}

		// Filter by type
		if factType != "" && fact.FactType != factType {
			continue
		}

		// Filter by confidence
		if fact.Confidence < minConfidence {
			continue
		}

		// Filter by search term
		if search != "" {
			searchLower := strings.ToLower(search)
			if !strings.Contains(strings.ToLower(fact.Claim), searchLower) &&
				!containsInSlice(fact.Entities, searchLower) &&
				!containsInSlice(fact.QuantitativeValues, searchLower) {
				continue
			}
		}

		filtered = append(filtered, fact)
	}

	// Paginate
	total := len(filtered)
	totalPages := (total + pageSize - 1) / pageSize
	if page < 1 {
		page = 1
	}
	if page > totalPages && totalPages > 0 {
		page = totalPages
	}

	start := (page - 1) * pageSize
	end := start + pageSize
	if start > total {
		start = total
	}
	if end > total {
		end = total
	}

	paged := filtered[start:end]
	if paged == nil {
		paged = []models.ExtractedFact{}
	}

	writeJSON(w, http.StatusOK, FactsListResponse{
		Facts:      paged,
		Total:      total,
		Page:       page,
		PageSize:   pageSize,
		TotalPages: totalPages,
	})
}

// GetContext returns a fact with its source context
func (h *FactsHandler) GetContext(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("id")
	factIndexStr := r.PathValue("n")

	if sessionID == "" {
		writeError(w, http.StatusBadRequest, "Session ID is required")
		return
	}

	factIndex, err := strconv.Atoi(factIndexStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, "Invalid fact index")
		return
	}

	// Load all facts
	facts, err := h.store.LoadAllFacts(sessionID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Failed to load facts: "+err.Error())
		return
	}

	if factIndex < 0 || factIndex >= len(facts) {
		writeError(w, http.StatusNotFound, "Fact index out of range")
		return
	}

	fact := facts[factIndex]

	// Parse source location to get chunk info
	chunkID := parseChunkFromLocation(fact.SourceLocation)
	lineStart, lineEnd := parseLinesFromLocation(fact.SourceLocation)

	// Try to load chunk text
	var chunkText string
	if chunkID != "" {
		chunkText, _ = h.store.LoadChunkText(sessionID, fact.SourceDoc, chunkID)
	}

	// If no chunk text, try to load from document text and extract lines
	if chunkText == "" && lineStart > 0 {
		docText, err := h.store.LoadDocumentText(sessionID, fact.SourceDoc)
		if err == nil {
			chunkText = extractLines(docText, lineStart, lineEnd)
		}
	}

	// Find evidence quote positions for highlighting
	var highlights []HighlightRange
	for _, quote := range fact.GetAllQuotes() {
		if idx := strings.Index(chunkText, quote); idx >= 0 {
			highlights = append(highlights, HighlightRange{
				Start: idx,
				End:   idx + len(quote),
				Quote: quote,
			})
		}
	}

	writeJSON(w, http.StatusOK, FactContextResponse{
		Fact:       fact,
		ChunkText:  chunkText,
		LineStart:  lineStart,
		LineEnd:    lineEnd,
		Highlights: highlights,
	})
}

// Helper functions

func parseInt(s string, defaultVal int) int {
	if s == "" {
		return defaultVal
	}
	if i, err := strconv.Atoi(s); err == nil {
		return i
	}
	return defaultVal
}

func parseFloat(s string, defaultVal float64) float64 {
	if s == "" {
		return defaultVal
	}
	if f, err := strconv.ParseFloat(s, 64); err == nil {
		return f
	}
	return defaultVal
}

func containsInSlice(slice []string, search string) bool {
	for _, s := range slice {
		if strings.Contains(strings.ToLower(s), search) {
			return true
		}
	}
	return false
}

// parseChunkFromLocation extracts chunk ID from source location like "chunk_0005"
func parseChunkFromLocation(location string) string {
	re := regexp.MustCompile(`chunk_\d+`)
	match := re.FindString(location)
	return match
}

// parseLinesFromLocation extracts line numbers from location like "Lines 42-45"
func parseLinesFromLocation(location string) (int, int) {
	re := regexp.MustCompile(`Lines?\s*(\d+)(?:\s*-\s*(\d+))?`)
	matches := re.FindStringSubmatch(location)
	if len(matches) < 2 {
		return 0, 0
	}

	start, _ := strconv.Atoi(matches[1])
	end := start
	if len(matches) > 2 && matches[2] != "" {
		end, _ = strconv.Atoi(matches[2])
	}
	return start, end
}

// extractLines extracts a range of lines from text
func extractLines(text string, start, end int) string {
	lines := strings.Split(text, "\n")
	if start < 1 {
		start = 1
	}
	if end < start {
		end = start
	}
	if start > len(lines) {
		return ""
	}
	if end > len(lines) {
		end = len(lines)
	}
	// Convert to 0-indexed
	return strings.Join(lines[start-1:end], "\n")
}
