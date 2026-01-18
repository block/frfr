package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/nesposito/frfr/internal/domain/models"
	"github.com/nesposito/frfr/internal/services/session"
)

// SessionHandler handles session-related API requests
type SessionHandler struct {
	store *session.Store
}

// NewSessionHandler creates a new session handler
func NewSessionHandler(store *session.Store) *SessionHandler {
	return &SessionHandler{store: store}
}

// CreateSessionRequest is the request body for creating a session
type CreateSessionRequest struct {
	Name          string   `json:"name,omitempty"`
	DocumentPaths []string `json:"document_paths,omitempty"`
}

// UpdateSessionRequest is the request body for updating a session
type UpdateSessionRequest struct {
	Name   string               `json:"name,omitempty"`
	Status models.SessionStatus `json:"status,omitempty"`
}

// List returns all sessions
func (h *SessionHandler) List(w http.ResponseWriter, r *http.Request) {
	sessions, err := h.store.List()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Failed to list sessions: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, sessions)
}

// Create creates a new session
func (h *SessionHandler) Create(w http.ResponseWriter, r *http.Request) {
	var req CreateSessionRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid request body: "+err.Error())
		return
	}

	// Generate session ID
	sessionID := generateSessionID(req.Name)

	session, err := h.store.Create(sessionID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Failed to create session: "+err.Error())
		return
	}

	// Add documents if provided
	for _, docPath := range req.DocumentPaths {
		docName := extractDocumentName(docPath)
		if err := h.store.AddDocument(sessionID, docName, docPath); err != nil {
			// Log but don't fail the request
			fmt.Printf("Warning: failed to add document %s: %v\n", docPath, err)
		}
	}

	// Reload session to get updated document registry
	if len(req.DocumentPaths) > 0 {
		session, _ = h.store.Get(sessionID)
	}

	writeJSON(w, http.StatusCreated, session)
}

// Get returns a specific session
func (h *SessionHandler) Get(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("id")
	if sessionID == "" {
		writeError(w, http.StatusBadRequest, "Session ID is required")
		return
	}

	session, err := h.store.Get(sessionID)
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			writeError(w, http.StatusNotFound, err.Error())
		} else {
			writeError(w, http.StatusInternalServerError, "Failed to get session: "+err.Error())
		}
		return
	}

	writeJSON(w, http.StatusOK, session)
}

// Delete removes a session
func (h *SessionHandler) Delete(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("id")
	if sessionID == "" {
		writeError(w, http.StatusBadRequest, "Session ID is required")
		return
	}

	if err := h.store.Delete(sessionID); err != nil {
		if strings.Contains(err.Error(), "not found") {
			writeError(w, http.StatusNotFound, err.Error())
		} else {
			writeError(w, http.StatusInternalServerError, "Failed to delete session: "+err.Error())
		}
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// Update updates a session
func (h *SessionHandler) Update(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("id")
	if sessionID == "" {
		writeError(w, http.StatusBadRequest, "Session ID is required")
		return
	}

	var req UpdateSessionRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid request body: "+err.Error())
		return
	}

	session, err := h.store.Get(sessionID)
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			writeError(w, http.StatusNotFound, err.Error())
		} else {
			writeError(w, http.StatusInternalServerError, "Failed to get session: "+err.Error())
		}
		return
	}

	// Handle rename
	if req.Name != "" && req.Name != session.GetName() {
		newSessionID := generateSessionID(req.Name)
		session, err = h.store.Rename(sessionID, newSessionID, fmt.Sprintf("Renamed from %s", sessionID))
		if err != nil {
			writeError(w, http.StatusInternalServerError, "Failed to rename session: "+err.Error())
			return
		}
	}

	// Update status if provided
	if req.Status != "" {
		session.Status = req.Status
		if err := h.store.Update(session); err != nil {
			writeError(w, http.StatusInternalServerError, "Failed to update session: "+err.Error())
			return
		}
	}

	writeJSON(w, http.StatusOK, session)
}

// generateSessionID creates a session ID from a name or generates one
func generateSessionID(name string) string {
	timestamp := time.Now().Format("20060102_150405")
	if name == "" {
		return fmt.Sprintf("sess_%s", timestamp)
	}
	// Sanitize name: lowercase, replace spaces/special chars with underscore
	sanitized := strings.ToLower(name)
	sanitized = strings.Map(func(r rune) rune {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			return r
		}
		return '_'
	}, sanitized)
	// Remove consecutive underscores and trim
	for strings.Contains(sanitized, "__") {
		sanitized = strings.ReplaceAll(sanitized, "__", "_")
	}
	sanitized = strings.Trim(sanitized, "_")
	if len(sanitized) > 30 {
		sanitized = sanitized[:30]
	}
	return fmt.Sprintf("sess_%s_%s", sanitized, timestamp)
}

// extractDocumentName extracts the document name from a file path
func extractDocumentName(path string) string {
	// Get the base filename
	parts := strings.Split(path, "/")
	filename := parts[len(parts)-1]
	// Remove extension
	if idx := strings.LastIndex(filename, "."); idx > 0 {
		filename = filename[:idx]
	}
	return filename
}
