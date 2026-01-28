package pdf

import (
	"context"
	"os"
	"path/filepath"
	"testing"
)

func TestExtractor_Extract(t *testing.T) {
	// Skip if no test PDF available
	testPDF := os.Getenv("TEST_PDF")
	if testPDF == "" {
		t.Skip("Set TEST_PDF environment variable to run this test")
	}

	extractor := NewExtractor("")
	defer extractor.Close()

	// Create temp output file
	tmpDir := t.TempDir()
	outputPath := filepath.Join(tmpDir, "output.txt")

	result, err := extractor.Extract(context.Background(), testPDF, outputPath)
	if err != nil {
		t.Fatalf("Extract failed: %v", err)
	}

	if result.Status != "success" {
		t.Errorf("Expected status 'success', got '%s'", result.Status)
	}

	if result.Method != "pdfium" {
		t.Errorf("Expected method 'pdfium', got '%s'", result.Method)
	}

	if result.Pages == 0 {
		t.Error("Expected non-zero page count")
	}

	if result.TotalChars == 0 {
		t.Error("Expected non-zero character count")
	}

	// Verify output file exists and has content
	content, err := os.ReadFile(outputPath)
	if err != nil {
		t.Fatalf("Failed to read output file: %v", err)
	}

	if len(content) == 0 {
		t.Error("Output file is empty")
	}

	t.Logf("Extracted %d pages, %d chars", result.Pages, result.TotalChars)
}

func TestExtractor_GetInfo(t *testing.T) {
	// Skip if no test PDF available
	testPDF := os.Getenv("TEST_PDF")
	if testPDF == "" {
		t.Skip("Set TEST_PDF environment variable to run this test")
	}

	extractor := NewExtractor("")
	defer extractor.Close()

	info, err := extractor.GetInfo(context.Background(), testPDF)
	if err != nil {
		t.Fatalf("GetInfo failed: %v", err)
	}

	if info.Status != "success" {
		t.Errorf("Expected status 'success', got '%s'", info.Status)
	}

	if info.Pages == 0 {
		t.Error("Expected non-zero page count")
	}

	if info.FileSize == 0 {
		t.Error("Expected non-zero file size")
	}

	t.Logf("PDF info: %d pages, %d bytes, encrypted=%v", info.Pages, info.FileSize, info.IsEncrypted)
}
