package pdf

import (
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"path/filepath"
	"time"
)

// ExtractionResult contains the result of PDF text extraction
type ExtractionResult struct {
	Status        string `json:"status"`
	Method        string `json:"method"`
	Pages         int    `json:"pages"`
	TotalChars    int    `json:"total_chars"`
	OutputFile    string `json:"output_file"`
	SourcePDF     string `json:"source_pdf"`
	SourcePDFPath string `json:"source_pdf_path"`
	Error         string `json:"error,omitempty"`
	ErrorType     string `json:"error_type,omitempty"`
}

// PDFInfo contains metadata about a PDF file
type PDFInfo struct {
	Status      string `json:"status"`
	Pages       int    `json:"pages"`
	IsEncrypted bool   `json:"is_encrypted"`
	FileSize    int64  `json:"file_size"`
	Error       string `json:"error,omitempty"`
	ErrorType   string `json:"error_type,omitempty"`
}

// Extractor handles PDF text extraction via Python subprocess
type Extractor struct {
	pythonPath      string
	extractorModule string
	timeout         time.Duration
}

// NewExtractor creates a new PDF extractor
func NewExtractor(pythonPath string) *Extractor {
	if pythonPath == "" {
		pythonPath = "python3"
	}
	return &Extractor{
		pythonPath:      pythonPath,
		extractorModule: "frfr_pdf.extractor",
		timeout:         10 * time.Minute,
	}
}

// WithTimeout sets the extraction timeout
func (e *Extractor) WithTimeout(timeout time.Duration) *Extractor {
	e.timeout = timeout
	return e
}

// WithModulePath sets a custom module path for the extractor
func (e *Extractor) WithModulePath(modulePath string) *Extractor {
	e.extractorModule = modulePath
	return e
}

// Extract extracts text from a PDF file
func (e *Extractor) Extract(ctx context.Context, pdfPath, outputPath string) (*ExtractionResult, error) {
	// Create context with timeout
	ctx, cancel := context.WithTimeout(ctx, e.timeout)
	defer cancel()

	// Build command
	args := []string{"-m", e.extractorModule, pdfPath, "--output", outputPath, "--json"}
	cmd := exec.CommandContext(ctx, e.pythonPath, args...)

	// Run and capture output
	output, err := cmd.Output()
	if err != nil {
		// Try to parse error output as JSON
		if exitErr, ok := err.(*exec.ExitError); ok {
			var result ExtractionResult
			if jsonErr := json.Unmarshal(exitErr.Stderr, &result); jsonErr == nil {
				return &result, fmt.Errorf("extraction failed: %s", result.Error)
			}
			// If stderr wasn't JSON, check stdout
			if len(output) > 0 {
				if jsonErr := json.Unmarshal(output, &result); jsonErr == nil && result.Status == "error" {
					return &result, fmt.Errorf("extraction failed: %s", result.Error)
				}
			}
		}
		return nil, fmt.Errorf("PDF extraction command failed: %w", err)
	}

	// Parse JSON output
	var result ExtractionResult
	if err := json.Unmarshal(output, &result); err != nil {
		return nil, fmt.Errorf("failed to parse extraction result: %w (output: %s)", err, string(output))
	}

	if result.Status == "error" {
		return &result, fmt.Errorf("extraction failed: %s", result.Error)
	}

	return &result, nil
}

// GetInfo gets metadata about a PDF file
func (e *Extractor) GetInfo(ctx context.Context, pdfPath string) (*PDFInfo, error) {
	// Create context with shorter timeout for info
	ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	// Build command
	args := []string{"-m", e.extractorModule, pdfPath, "--info-only", "--json"}
	cmd := exec.CommandContext(ctx, e.pythonPath, args...)

	// Run and capture output
	output, err := cmd.Output()
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			var info PDFInfo
			if jsonErr := json.Unmarshal(exitErr.Stderr, &info); jsonErr == nil {
				return &info, fmt.Errorf("failed to get PDF info: %s", info.Error)
			}
			if len(output) > 0 {
				if jsonErr := json.Unmarshal(output, &info); jsonErr == nil && info.Status == "error" {
					return &info, fmt.Errorf("failed to get PDF info: %s", info.Error)
				}
			}
		}
		return nil, fmt.Errorf("PDF info command failed: %w", err)
	}

	// Parse JSON output
	var info PDFInfo
	if err := json.Unmarshal(output, &info); err != nil {
		return nil, fmt.Errorf("failed to parse PDF info: %w (output: %s)", err, string(output))
	}

	if info.Status == "error" {
		return &info, fmt.Errorf("failed to get PDF info: %s", info.Error)
	}

	return &info, nil
}

// ExtractToSessionDir extracts PDF text and saves it to the session's text directory
func (e *Extractor) ExtractToSessionDir(ctx context.Context, pdfPath, sessionDir, docName string) (*ExtractionResult, error) {
	textDir := filepath.Join(sessionDir, "text")
	outputPath := filepath.Join(textDir, docName+".txt")
	return e.Extract(ctx, pdfPath, outputPath)
}
