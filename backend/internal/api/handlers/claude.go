package handlers

import (
	"encoding/json"
	"net/http"
	"os/exec"

	"github.com/nesposito/frfr/internal/config"
)

// ClaudeHandler handles Claude-related endpoints
type ClaudeHandler struct {
	config *config.Config
}

// NewClaudeHandler creates a new Claude handler
func NewClaudeHandler(cfg *config.Config) *ClaudeHandler {
	return &ClaudeHandler{config: cfg}
}

// ClaudeStatusResponse represents the Claude availability status
type ClaudeStatusResponse struct {
	Available bool   `json:"available"`
	Mode      string `json:"mode"` // "api", "native", or ""
	Error     string `json:"error,omitempty"`
}

// Status checks if Claude is available and returns the mode
func (h *ClaudeHandler) Status(w http.ResponseWriter, r *http.Request) {
	response := ClaudeStatusResponse{}

	// Check if API key is configured
	if h.config.AnthropicAPIKey != "" {
		response.Available = true
		response.Mode = "api"
		writeJSON(w, http.StatusOK, response)
		return
	}

	// No API key - check if claude CLI is available
	_, err := exec.LookPath("claude")
	if err == nil {
		response.Available = true
		response.Mode = "native"
		writeJSON(w, http.StatusOK, response)
		return
	}

	// Neither API key nor CLI available
	response.Available = false
	response.Error = "Claude is not configured. Set ANTHROPIC_API_KEY environment variable or install the Claude CLI."
	writeJSON(w, http.StatusOK, response)
}

// SetFastMode toggles fast mode at runtime without a restart
func (h *ClaudeHandler) SetFastMode(w http.ResponseWriter, r *http.Request) {
	var req struct {
		FastMode bool `json:"fastMode"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}
	h.config.SetFastMode(req.FastMode)
	writeJSON(w, http.StatusOK, map[string]bool{"fastMode": req.FastMode})
}
