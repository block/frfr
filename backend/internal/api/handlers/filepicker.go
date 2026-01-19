package handlers

import (
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// FilePickerHandler handles file picker API requests
type FilePickerHandler struct{}

// NewFilePickerHandler creates a new file picker handler
func NewFilePickerHandler() *FilePickerHandler {
	return &FilePickerHandler{}
}

// FilePickerResponse is the response from the file picker
type FilePickerResponse struct {
	Files []string `json:"files"`
}

// Pick opens the native macOS file picker and returns selected files
func (h *FilePickerHandler) Pick(w http.ResponseWriter, r *http.Request) {
	// Get initial directory from query param, default to home
	initialDir := r.URL.Query().Get("dir")
	if initialDir == "" {
		home, _ := os.UserHomeDir()
		initialDir = home
	}

	// Build AppleScript for native file picker
	script := `
set theFiles to choose file with prompt "Select PDF Files" of type {"pdf", "txt", "md", "markdown"} default location (POSIX file "` + initialDir + `") with multiple selections allowed

set thePaths to {}
repeat with aFile in theFiles
    set end of thePaths to POSIX path of aFile
end repeat

set AppleScript's text item delimiters to linefeed
set pathList to thePaths as text
return pathList
`

	// Execute AppleScript
	cmd := exec.Command("osascript", "-e", script)
	output, err := cmd.Output()

	// User cancelled or error
	if err != nil {
		// Return empty list (not an error - user just cancelled)
		writeJSON(w, http.StatusOK, FilePickerResponse{Files: []string{}})
		return
	}

	// Parse output - paths are separated by newlines
	outputStr := strings.TrimSpace(string(output))
	var files []string
	if outputStr != "" {
		for _, path := range strings.Split(outputStr, "\n") {
			path = strings.TrimSpace(path)
			if path != "" {
				// Clean the path
				path = filepath.Clean(path)
				files = append(files, path)
			}
		}
	}

	writeJSON(w, http.StatusOK, FilePickerResponse{Files: files})
}
