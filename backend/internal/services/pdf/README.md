# PDF Text Extraction

This package extracts text from PDF files using [go-pdfium](https://github.com/klippa-app/go-pdfium), a Go wrapper around Google's PDFium library via WebAssembly.

## Usage

```go
extractor := pdf.NewExtractor("")
defer extractor.Close()

// Extract text to file
result, err := extractor.Extract(ctx, "/path/to/input.pdf", "/path/to/output.txt")

// Get PDF metadata
info, err := extractor.GetInfo(ctx, "/path/to/input.pdf")

// Extract to session directory
result, err := extractor.ExtractToSessionDir(ctx, pdfPath, sessionDir, docName)
```

## Implementation Notes

- Uses WebAssembly runtime (no CGO, no external dependencies)
- Global pool with lazy initialization for efficiency
- Page breaks marked with `=== PAGE BREAK ===` between pages
- The `pythonPath` parameter in `NewExtractor()` is ignored (kept for backwards compatibility)

## History

Originally used Python subprocess calling pdfplumber. Replaced in Jan 2025 with go-pdfium after testing showed:

| Metric | Python (pdfplumber) | Go (pdfium) |
|--------|---------------------|-------------|
| Speed | baseline | 12-17x faster |
| Text similarity | baseline | 92-97% |
| Encrypted PDF support | Yes | Yes |
| External dependencies | Python + pdfplumber | None |

Testing was done using `cmd/pdf-compare` against 5 PDFs (6-155 pages) comparing Python pdfplumber, ledongthuc/pdf, and go-pdfium.
