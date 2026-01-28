package pdf

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/klippa-app/go-pdfium"
	"github.com/klippa-app/go-pdfium/requests"
	"github.com/klippa-app/go-pdfium/webassembly"
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

// Extractor handles PDF text extraction using go-pdfium (WebAssembly)
type Extractor struct {
	pool     pdfium.Pool
	instance pdfium.Pdfium
	timeout  time.Duration
	initOnce sync.Once
	initErr  error
}

// Global pool for reuse across extractors
var (
	globalPool     pdfium.Pool
	globalPoolOnce sync.Once
	globalPoolErr  error
)

// initGlobalPool initializes the shared pdfium pool
func initGlobalPool() (pdfium.Pool, error) {
	globalPoolOnce.Do(func() {
		globalPool, globalPoolErr = webassembly.Init(webassembly.Config{
			MinIdle:  1,
			MaxIdle:  2,
			MaxTotal: 4,
		})
	})
	return globalPool, globalPoolErr
}

// NewExtractor creates a new PDF extractor
// The pythonPath parameter is kept for backwards compatibility but is ignored
func NewExtractor(pythonPath string) *Extractor {
	return &Extractor{
		timeout: 10 * time.Minute,
	}
}

// init lazily initializes the pdfium instance
func (e *Extractor) init() error {
	e.initOnce.Do(func() {
		e.pool, e.initErr = initGlobalPool()
		if e.initErr != nil {
			return
		}
		e.instance, e.initErr = e.pool.GetInstance(time.Second * 30)
	})
	return e.initErr
}

// WithTimeout sets the extraction timeout
func (e *Extractor) WithTimeout(timeout time.Duration) *Extractor {
	e.timeout = timeout
	return e
}

// WithModulePath is kept for backwards compatibility but is a no-op
// (was used for Python module path)
func (e *Extractor) WithModulePath(modulePath string) *Extractor {
	return e
}

// Extract extracts text from a PDF file and saves it to outputPath
func (e *Extractor) Extract(ctx context.Context, pdfPath, outputPath string) (*ExtractionResult, error) {
	if err := e.init(); err != nil {
		return &ExtractionResult{
			Status:    "error",
			Error:     fmt.Sprintf("failed to initialize PDF extractor: %v", err),
			ErrorType: "init_failed",
		}, fmt.Errorf("failed to initialize PDF extractor: %w", err)
	}

	// Create context with timeout
	ctx, cancel := context.WithTimeout(ctx, e.timeout)
	defer cancel()

	// Read the PDF file
	pdfBytes, err := os.ReadFile(pdfPath)
	if err != nil {
		return &ExtractionResult{
			Status:        "error",
			Error:         fmt.Sprintf("failed to read PDF file: %v", err),
			ErrorType:     "file_not_found",
			SourcePDF:     filepath.Base(pdfPath),
			SourcePDFPath: pdfPath,
		}, fmt.Errorf("failed to read PDF file: %w", err)
	}

	// Open the document
	doc, err := e.instance.OpenDocument(&requests.OpenDocument{
		File: &pdfBytes,
	})
	if err != nil {
		return &ExtractionResult{
			Status:        "error",
			Error:         fmt.Sprintf("failed to open PDF document: %v", err),
			ErrorType:     "open_failed",
			SourcePDF:     filepath.Base(pdfPath),
			SourcePDFPath: pdfPath,
		}, fmt.Errorf("failed to open PDF document: %w", err)
	}
	defer e.instance.FPDF_CloseDocument(&requests.FPDF_CloseDocument{
		Document: doc.Document,
	})

	// Get page count
	pageCountResp, err := e.instance.FPDF_GetPageCount(&requests.FPDF_GetPageCount{
		Document: doc.Document,
	})
	if err != nil {
		return &ExtractionResult{
			Status:        "error",
			Error:         fmt.Sprintf("failed to get page count: %v", err),
			ErrorType:     "extraction_failed",
			SourcePDF:     filepath.Base(pdfPath),
			SourcePDFPath: pdfPath,
		}, fmt.Errorf("failed to get page count: %w", err)
	}

	numPages := pageCountResp.PageCount
	var buf bytes.Buffer

	// Extract text from each page
	for i := 0; i < numPages; i++ {
		// Check context cancellation
		select {
		case <-ctx.Done():
			return &ExtractionResult{
				Status:        "error",
				Error:         "extraction timeout or cancelled",
				ErrorType:     "timeout",
				SourcePDF:     filepath.Base(pdfPath),
				SourcePDFPath: pdfPath,
			}, ctx.Err()
		default:
		}

		textResp, err := e.instance.GetPageText(&requests.GetPageText{
			Page: requests.Page{
				ByIndex: &requests.PageByIndex{
					Document: doc.Document,
					Index:    i,
				},
			},
		})
		if err != nil {
			// Log warning but continue with other pages
			continue
		}

		buf.WriteString(textResp.Text)

		// Add page break marker between pages (matching Python output format)
		if i < numPages-1 {
			buf.WriteString("\n\n=== PAGE BREAK ===\n\n")
		}
	}

	// Ensure output directory exists
	outputDir := filepath.Dir(outputPath)
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return &ExtractionResult{
			Status:        "error",
			Error:         fmt.Sprintf("failed to create output directory: %v", err),
			ErrorType:     "io_error",
			SourcePDF:     filepath.Base(pdfPath),
			SourcePDFPath: pdfPath,
		}, fmt.Errorf("failed to create output directory: %w", err)
	}

	// Write extracted text to file
	text := buf.String()
	if err := os.WriteFile(outputPath, []byte(text), 0644); err != nil {
		return &ExtractionResult{
			Status:        "error",
			Error:         fmt.Sprintf("failed to write output file: %v", err),
			ErrorType:     "io_error",
			SourcePDF:     filepath.Base(pdfPath),
			SourcePDFPath: pdfPath,
		}, fmt.Errorf("failed to write output file: %w", err)
	}

	absOutputPath, _ := filepath.Abs(outputPath)
	absPdfPath, _ := filepath.Abs(pdfPath)

	return &ExtractionResult{
		Status:        "success",
		Method:        "pdfium",
		Pages:         numPages,
		TotalChars:    len(text),
		OutputFile:    absOutputPath,
		SourcePDF:     filepath.Base(pdfPath),
		SourcePDFPath: absPdfPath,
	}, nil
}

// GetInfo gets metadata about a PDF file
func (e *Extractor) GetInfo(ctx context.Context, pdfPath string) (*PDFInfo, error) {
	if err := e.init(); err != nil {
		return &PDFInfo{
			Status:    "error",
			Error:     fmt.Sprintf("failed to initialize PDF extractor: %v", err),
			ErrorType: "init_failed",
		}, fmt.Errorf("failed to initialize PDF extractor: %w", err)
	}

	// Create context with shorter timeout for info
	ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	// Get file info
	fileInfo, err := os.Stat(pdfPath)
	if err != nil {
		return &PDFInfo{
			Status:    "error",
			Error:     fmt.Sprintf("failed to stat PDF file: %v", err),
			ErrorType: "file_not_found",
		}, fmt.Errorf("failed to stat PDF file: %w", err)
	}

	// Read the PDF file
	pdfBytes, err := os.ReadFile(pdfPath)
	if err != nil {
		return &PDFInfo{
			Status:    "error",
			Error:     fmt.Sprintf("failed to read PDF file: %v", err),
			ErrorType: "file_not_found",
		}, fmt.Errorf("failed to read PDF file: %w", err)
	}

	// Try to open the document
	doc, err := e.instance.OpenDocument(&requests.OpenDocument{
		File: &pdfBytes,
	})
	if err != nil {
		// Check if it's an encryption error
		return &PDFInfo{
			Status:      "error",
			Error:       fmt.Sprintf("failed to open PDF document: %v", err),
			ErrorType:   "open_failed",
			FileSize:    fileInfo.Size(),
			IsEncrypted: true, // Assume encrypted if we can't open
		}, fmt.Errorf("failed to open PDF document: %w", err)
	}
	defer e.instance.FPDF_CloseDocument(&requests.FPDF_CloseDocument{
		Document: doc.Document,
	})

	// Get page count
	pageCountResp, err := e.instance.FPDF_GetPageCount(&requests.FPDF_GetPageCount{
		Document: doc.Document,
	})
	if err != nil {
		return &PDFInfo{
			Status:    "error",
			Error:     fmt.Sprintf("failed to get page count: %v", err),
			ErrorType: "extraction_failed",
			FileSize:  fileInfo.Size(),
		}, fmt.Errorf("failed to get page count: %w", err)
	}

	return &PDFInfo{
		Status:      "success",
		Pages:       pageCountResp.PageCount,
		IsEncrypted: false,
		FileSize:    fileInfo.Size(),
	}, nil
}

// ExtractToSessionDir extracts PDF text and saves it to the session's text directory
func (e *Extractor) ExtractToSessionDir(ctx context.Context, pdfPath, sessionDir, docName string) (*ExtractionResult, error) {
	textDir := filepath.Join(sessionDir, "text")
	outputPath := filepath.Join(textDir, docName+".txt")
	return e.Extract(ctx, pdfPath, outputPath)
}

// Close releases the pdfium instance back to the pool
// Note: The global pool is not closed to allow reuse
func (e *Extractor) Close() error {
	if e.instance != nil {
		return e.instance.Close()
	}
	return nil
}
