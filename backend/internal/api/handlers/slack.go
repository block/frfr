package handlers

import (
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/nesposito/frfr/internal/domain/models"
	"github.com/nesposito/frfr/internal/services/session"
)

// SlackHandler handles Slack-related API requests
type SlackHandler struct {
	store *session.Store
}

// NewSlackHandler creates a new Slack handler
func NewSlackHandler(store *session.Store) *SlackHandler {
	return &SlackHandler{store: store}
}

// AddSlackChannelRequest is the request body for importing a Slack channel
type AddSlackChannelRequest struct {
	ChannelID string `json:"channel_id"`
	Token     string `json:"token,omitempty"` // Optional; falls back to SLACK_BOT_TOKEN env
	Since     string `json:"since,omitempty"` // Date string: "2025-01-01"
	Until     string `json:"until,omitempty"` // Date string: "2025-03-01"
}

// Add imports a Slack channel as a document source in a session
func (h *SlackHandler) Add(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("id")
	if sessionID == "" {
		writeError(w, http.StatusBadRequest, "Session ID is required")
		return
	}

	var req AddSlackChannelRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid request body: "+err.Error())
		return
	}

	if req.ChannelID == "" {
		writeError(w, http.StatusBadRequest, "channel_id is required")
		return
	}

	// Check that we have a token somewhere
	token := req.Token
	if token == "" {
		token = os.Getenv("SLACK_BOT_TOKEN")
	}
	if token == "" {
		writeError(w, http.StatusBadRequest, "No Slack token provided. Set SLACK_BOT_TOKEN env or pass 'token' in request.")
		return
	}

	// Get session
	sess, err := h.store.Get(sessionID)
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			writeError(w, http.StatusNotFound, err.Error())
		} else {
			writeError(w, http.StatusInternalServerError, "Failed to get session: "+err.Error())
		}
		return
	}

	// Create document name from channel ID
	docName := "slack-" + req.ChannelID

	// Register as a document in the session
	if sess.DocumentRegistry == nil {
		sess.DocumentRegistry = make(map[string]models.DocumentInfo)
	}

	sess.DocumentRegistry[docName] = models.DocumentInfo{
		Status:  models.DocumentStatusPending,
		AddedAt: models.FlexibleTime{Time: time.Now()},
		Source:  models.DocumentSourceSlack,
		SlackMeta: &models.SlackDocumentMeta{
			ChannelID: req.ChannelID,
			Since:     req.Since,
			Until:     req.Until,
		},
	}

	if err := h.store.Update(sess); err != nil {
		writeError(w, http.StatusInternalServerError, "Failed to update session: "+err.Error())
		return
	}

	writeJSON(w, http.StatusCreated, sess.DocumentRegistry[docName])
}
