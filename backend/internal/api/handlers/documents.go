package handlers

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/nesposito/frfr/internal/config"
	"github.com/nesposito/frfr/internal/domain/models"
	"github.com/nesposito/frfr/internal/services/session"
)

// DocumentHandler handles document-related API requests
type DocumentHandler struct {
	store  *session.Store
	config *config.Config
}

// NewDocumentHandler creates a new document handler
func NewDocumentHandler(store *session.Store, cfg *config.Config) *DocumentHandler {
	return &DocumentHandler{store: store, config: cfg}
}

// AddDocumentRequest is the request body for adding a document
type AddDocumentRequest struct {
	Path string `json:"path"`
	Name string `json:"name,omitempty"`
}

// DocumentListItem represents a document in the list response
type DocumentListItem struct {
	Name         string                `json:"name"`
	Status       models.DocumentStatus `json:"status"`
	FactCount    int                   `json:"fact_count"`
	OriginalPath string                `json:"original_path"`
	AddedAt      string                `json:"added_at"`
	CompletedAt  *string               `json:"completed_at,omitempty"`
	Error        string                `json:"error,omitempty"`
}

// List returns all documents in a session
func (h *DocumentHandler) List(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("id")
	if sessionID == "" {
		writeError(w, http.StatusBadRequest, "Session ID is required")
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

	var docs []DocumentListItem
	for name, info := range sess.DocumentRegistry {
		facts, _ := h.store.LoadDocumentFacts(sessionID, name)

		item := DocumentListItem{
			Name:         name,
			Status:       info.Status,
			FactCount:    len(facts),
			OriginalPath: info.OriginalPDFPath,
			AddedAt:      info.AddedAt.Format("2006-01-02T15:04:05Z07:00"),
			Error:        info.ErrorMessage,
		}
		if info.CompletedAt != nil {
			completedStr := info.CompletedAt.Format("2006-01-02T15:04:05Z07:00")
			item.CompletedAt = &completedStr
		}
		docs = append(docs, item)
	}

	writeJSON(w, http.StatusOK, docs)
}

// Add adds a document to a session
func (h *DocumentHandler) Add(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("id")
	if sessionID == "" {
		writeError(w, http.StatusBadRequest, "Session ID is required")
		return
	}

	var req AddDocumentRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid request body: "+err.Error())
		return
	}

	if req.Path == "" {
		writeError(w, http.StatusBadRequest, "Document path is required")
		return
	}

	// Use provided name or extract from path
	docName := req.Name
	if docName == "" {
		docName = extractDocumentName(req.Path)
	}

	if err := h.store.AddDocument(sessionID, docName, req.Path); err != nil {
		if strings.Contains(err.Error(), "not found") {
			writeError(w, http.StatusNotFound, err.Error())
		} else {
			writeError(w, http.StatusInternalServerError, "Failed to add document: "+err.Error())
		}
		return
	}

	// Return updated session
	sess, err := h.store.Get(sessionID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Failed to get session: "+err.Error())
		return
	}

	writeJSON(w, http.StatusCreated, sess.DocumentRegistry[docName])
}

// Reprocess triggers reprocessing of a document
func (h *DocumentHandler) Reprocess(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("id")
	docName := r.PathValue("doc")

	if sessionID == "" {
		writeError(w, http.StatusBadRequest, "Session ID is required")
		return
	}
	if docName == "" {
		writeError(w, http.StatusBadRequest, "Document name is required")
		return
	}

	// Check session and document exist
	sess, err := h.store.Get(sessionID)
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			writeError(w, http.StatusNotFound, err.Error())
		} else {
			writeError(w, http.StatusInternalServerError, "Failed to get session: "+err.Error())
		}
		return
	}

	if _, ok := sess.DocumentRegistry[docName]; !ok {
		writeError(w, http.StatusNotFound, "Document not found in session")
		return
	}

	// Reset document status to pending
	if err := h.store.UpdateDocumentStatus(sessionID, docName, models.DocumentStatusPending, ""); err != nil {
		writeError(w, http.StatusInternalServerError, "Failed to update document status: "+err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{
		"status":  "pending",
		"message": "Document queued for reprocessing",
	})
}
