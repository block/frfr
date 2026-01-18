package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/nesposito/frfr/internal/config"
	"github.com/nesposito/frfr/internal/domain/models"
	"github.com/nesposito/frfr/internal/services/claude"
	"github.com/nesposito/frfr/internal/services/extraction"
	"github.com/nesposito/frfr/internal/services/pdf"
	"github.com/nesposito/frfr/internal/services/session"
)

// ProcessingHandler handles processing-related API requests
type ProcessingHandler struct {
	store        *session.Store
	config       *config.Config
	pdfExtractor *pdf.Extractor
	subscribers  map[string][]chan models.ProcessingEvent
	mu           sync.RWMutex
}

// NewProcessingHandler creates a new processing handler
func NewProcessingHandler(store *session.Store, cfg *config.Config) *ProcessingHandler {
	return &ProcessingHandler{
		store:        store,
		config:       cfg,
		pdfExtractor: pdf.NewExtractor(cfg.PythonPath),
		subscribers:  make(map[string][]chan models.ProcessingEvent),
	}
}

// StartProcessingRequest is the request body for starting processing
type StartProcessingRequest struct {
	Documents []string `json:"documents,omitempty"` // Empty means process all pending
	Force     bool     `json:"force,omitempty"`     // Reprocess even if completed
}

// Start initiates document processing
func (h *ProcessingHandler) Start(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("id")
	if sessionID == "" {
		writeError(w, http.StatusBadRequest, "Session ID is required")
		return
	}

	var req StartProcessingRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil && r.ContentLength > 0 {
		writeError(w, http.StatusBadRequest, "Invalid request body: "+err.Error())
		return
	}

	sess, err := h.store.Get(sessionID)
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			writeError(w, http.StatusNotFound, err.Error())
		} else {
			writeError(w, http.StatusInternalServerError, "Failed to get session: "+err.Error())
		}
		return
	}

	// Determine which documents to process
	var docsToProcess []string
	if len(req.Documents) > 0 {
		docsToProcess = req.Documents
	} else {
		for name, doc := range sess.DocumentRegistry {
			if req.Force || doc.Status == models.DocumentStatusPending || doc.Status == models.DocumentStatusFailed {
				docsToProcess = append(docsToProcess, name)
			}
		}
	}

	if len(docsToProcess) == 0 {
		writeJSON(w, http.StatusOK, map[string]interface{}{
			"status":    "no_work",
			"message":   "No documents need processing",
			"documents": []string{},
		})
		return
	}

	// Update session status
	sess.Status = models.SessionStatusProcessing
	h.store.Update(sess)

	// Start processing in background
	go h.processDocuments(sessionID, docsToProcess)

	writeJSON(w, http.StatusAccepted, map[string]interface{}{
		"status":    "started",
		"message":   fmt.Sprintf("Processing %d document(s)", len(docsToProcess)),
		"documents": docsToProcess,
	})
}

// Events handles SSE for real-time processing updates
func (h *ProcessingHandler) Events(w http.ResponseWriter, r *http.Request) {
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

	// Set SSE headers
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	// Create event channel for this subscriber
	eventChan := make(chan models.ProcessingEvent, 100)

	// Register subscriber
	h.mu.Lock()
	h.subscribers[sessionID] = append(h.subscribers[sessionID], eventChan)
	h.mu.Unlock()

	// Clean up on disconnect
	defer func() {
		h.mu.Lock()
		subs := h.subscribers[sessionID]
		for i, ch := range subs {
			if ch == eventChan {
				h.subscribers[sessionID] = append(subs[:i], subs[i+1:]...)
				break
			}
		}
		h.mu.Unlock()
		close(eventChan)
	}()

	// Flush if available
	flusher, ok := w.(http.Flusher)
	if !ok {
		writeError(w, http.StatusInternalServerError, "Streaming not supported")
		return
	}

	// Send initial connection event
	h.sendSSE(w, flusher, models.ProcessingEvent{
		Type:      "connected",
		Timestamp: time.Now(),
		Message:   "Connected to processing events",
	})

	// Stream events
	for {
		select {
		case event := <-eventChan:
			h.sendSSE(w, flusher, event)
			if event.Type == models.EventTypeComplete {
				return
			}
		case <-r.Context().Done():
			return
		case <-time.After(30 * time.Second):
			// Send keepalive
			h.sendSSE(w, flusher, models.ProcessingEvent{
				Type:      "keepalive",
				Timestamp: time.Now(),
			})
		}
	}
}

// sendSSE sends an SSE event
func (h *ProcessingHandler) sendSSE(w http.ResponseWriter, flusher http.Flusher, event models.ProcessingEvent) {
	data, _ := json.Marshal(event)
	fmt.Fprintf(w, "data: %s\n\n", data)
	flusher.Flush()
}

// broadcast sends an event to all subscribers for a session
func (h *ProcessingHandler) broadcast(sessionID string, event models.ProcessingEvent) {
	h.mu.RLock()
	subs := h.subscribers[sessionID]
	h.mu.RUnlock()

	for _, ch := range subs {
		select {
		case ch <- event:
		default:
			// Channel full, skip
		}
	}
}

// processDocuments processes documents with PDF extraction and fact extraction
func (h *ProcessingHandler) processDocuments(sessionID string, documents []string) {
	ctx := context.Background()
	sessionDir := h.store.GetSessionDir(sessionID)

	// Get session for document info
	sess, err := h.store.Get(sessionID)
	if err != nil {
		h.broadcast(sessionID, models.ProcessingEvent{
			Type:      models.EventTypeError,
			Timestamp: time.Now(),
			Message:   fmt.Sprintf("Failed to load session: %v", err),
		})
		return
	}

	// Create Claude client (uses API key if available, otherwise tries native credentials)
	claudeClient := claude.NewClient(h.config.AnthropicAPIKey)

	totalDocs := len(documents)
	for i, docName := range documents {
		docInfo, ok := sess.DocumentRegistry[docName]
		if !ok {
			h.broadcast(sessionID, models.ProcessingEvent{
				Type:      models.EventTypeError,
				Timestamp: time.Now(),
				Document:  docName,
				Message:   fmt.Sprintf("Document %s not found in registry", docName),
			})
			continue
		}

		h.broadcast(sessionID, models.ProcessingEvent{
			Type:      models.EventTypeDocStart,
			Timestamp: time.Now(),
			Document:  docName,
			Message:   fmt.Sprintf("Starting document %d of %d: %s", i+1, totalDocs, docName),
			Progress:  float64(i) / float64(totalDocs),
		})

		// Update document status
		h.store.UpdateDocumentStatus(sessionID, docName, models.DocumentStatusProcessing, "")

		// Step 1: Extract text from PDF (if it's a PDF)
		var textContent string
		textFile := filepath.Join(sessionDir, "text", docName+".txt")

		if strings.HasSuffix(strings.ToLower(docInfo.OriginalPDFPath), ".pdf") {
			h.broadcast(sessionID, models.ProcessingEvent{
				Type:      "pdf_extraction_start",
				Timestamp: time.Now(),
				Document:  docName,
				Message:   "Extracting text from PDF...",
			})

			result, err := h.pdfExtractor.Extract(ctx, docInfo.OriginalPDFPath, textFile)
			if err != nil {
				h.store.UpdateDocumentStatus(sessionID, docName, models.DocumentStatusFailed, err.Error())
				h.broadcast(sessionID, models.ProcessingEvent{
					Type:      models.EventTypeError,
					Timestamp: time.Now(),
					Document:  docName,
					Message:   fmt.Sprintf("PDF extraction failed: %v", err),
				})
				continue
			}

			h.broadcast(sessionID, models.ProcessingEvent{
				Type:      "pdf_extraction_complete",
				Timestamp: time.Now(),
				Document:  docName,
				Message:   fmt.Sprintf("Extracted %d pages, %d characters using %s", result.Pages, result.TotalChars, result.Method),
			})

			// Read the extracted text
			data, err := os.ReadFile(textFile)
			if err != nil {
				h.store.UpdateDocumentStatus(sessionID, docName, models.DocumentStatusFailed, err.Error())
				h.broadcast(sessionID, models.ProcessingEvent{
					Type:      models.EventTypeError,
					Timestamp: time.Now(),
					Document:  docName,
					Message:   fmt.Sprintf("Failed to read extracted text: %v", err),
				})
				continue
			}
			textContent = string(data)
		} else {
			// For non-PDF files, try to read directly
			data, err := os.ReadFile(docInfo.OriginalPDFPath)
			if err != nil {
				h.store.UpdateDocumentStatus(sessionID, docName, models.DocumentStatusFailed, err.Error())
				h.broadcast(sessionID, models.ProcessingEvent{
					Type:      models.EventTypeError,
					Timestamp: time.Now(),
					Document:  docName,
					Message:   fmt.Sprintf("Failed to read file: %v", err),
				})
				continue
			}
			textContent = string(data)

			// Save to text directory
			os.MkdirAll(filepath.Dir(textFile), 0755)
			os.WriteFile(textFile, data, 0644)
		}

		// Step 2: Generate document summary and extract facts
		extractor := extraction.NewExtractor(claudeClient, h.config.MaxWorkers)
		{

			// Generate summary
			h.broadcast(sessionID, models.ProcessingEvent{
				Type:      models.EventTypeSummaryStart,
				Timestamp: time.Now(),
				Document:  docName,
				Message:   "Generating document summary...",
			})

			summary, err := extractor.SummarizeDocument(ctx, textContent, docName)
			if err != nil {
				h.broadcast(sessionID, models.ProcessingEvent{
					Type:      models.EventTypeError,
					Timestamp: time.Now(),
					Document:  docName,
					Message:   fmt.Sprintf("Summary generation failed: %v (continuing without summary)", err),
				})
			} else {
				h.store.SaveDocumentSummary(sessionID, docName, summary)
				h.broadcast(sessionID, models.ProcessingEvent{
					Type:      models.EventTypeSummaryDone,
					Timestamp: time.Now(),
					Document:  docName,
					Message:   fmt.Sprintf("Summary complete: %s document", summary.DocumentType),
				})
			}

			// Extract facts with progress reporting
			progressChan := make(chan extraction.ExtractionProgress, 100)
			go func() {
				for progress := range progressChan {
					h.broadcast(sessionID, models.ProcessingEvent{
						Type:      models.EventTypeChunkComplete,
						Timestamp: time.Now(),
						Document:  docName,
						ChunkID:   progress.ChunkID,
						Message:   progress.Message,
						Data: map[string]interface{}{
							"facts_extracted": progress.FactsExtracted,
						},
					})
				}
			}()

			results, err := extractor.ExtractFacts(ctx, textContent, docName, summary, progressChan)
			close(progressChan)

			if err != nil {
				h.store.UpdateDocumentStatus(sessionID, docName, models.DocumentStatusFailed, err.Error())
				h.broadcast(sessionID, models.ProcessingEvent{
					Type:      models.EventTypeError,
					Timestamp: time.Now(),
					Document:  docName,
					Message:   fmt.Sprintf("Fact extraction failed: %v", err),
				})
				continue
			}

			// Save facts and chunks
			totalFacts := 0
			for _, result := range results {
				h.store.SaveChunkFacts(sessionID, docName, result.ChunkID, result.Facts)
				totalFacts += len(result.Facts)
			}

			h.broadcast(sessionID, models.ProcessingEvent{
				Type:      models.EventTypeDocComplete,
				Timestamp: time.Now(),
				Document:  docName,
				Message:   fmt.Sprintf("Extracted %d facts from %d chunks", totalFacts, len(results)),
				Progress:  float64(i+1) / float64(totalDocs),
			})
		}

		h.store.UpdateDocumentStatus(sessionID, docName, models.DocumentStatusCompleted, "")
	}

	// Update session status
	sess, _ = h.store.Get(sessionID)
	if sess != nil {
		sess.Status = models.SessionStatusCompleted
		h.store.Update(sess)
	}

	h.broadcast(sessionID, models.ProcessingEvent{
		Type:      models.EventTypeComplete,
		Timestamp: time.Now(),
		Message:   fmt.Sprintf("Processing complete: %d documents", totalDocs),
		Progress:  1.0,
	})
}
