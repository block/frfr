package extraction

import (
	"strings"

	"github.com/nesposito/frfr/internal/domain/models"
)

// Chunker handles text chunking for document processing
type Chunker struct {
	MinChunkChars    int
	MaxChunkChars    int
	AdaptiveChunking bool
	// Legacy settings (when AdaptiveChunking=false)
	ChunkSize   int
	OverlapSize int
}

// NewChunker creates a new chunker with default settings
func NewChunker() *Chunker {
	return &Chunker{
		MinChunkChars:    3000,
		MaxChunkChars:    8000,
		AdaptiveChunking: true,
		ChunkSize:        50,
		OverlapSize:      10,
	}
}

// ChunkText splits text into overlapping chunks
func (c *Chunker) ChunkText(text string) []models.ChunkInfo {
	if c.AdaptiveChunking {
		return c.adaptiveChunkText(text)
	}
	return c.legacyChunkText(text)
}

// adaptiveChunkText implements adaptive character-based chunking with semantic boundaries
func (c *Chunker) adaptiveChunkText(text string) []models.ChunkInfo {
	totalChars := len(text)
	lines := strings.Split(text, "\n")

	// Calculate optimal number of chunks
	var optimalChunks int
	if totalChars <= c.MinChunkChars {
		optimalChunks = 1
	} else {
		optimalChunks = max(1, totalChars/c.MaxChunkChars)
		if totalChars/optimalChunks < c.MinChunkChars {
			optimalChunks = max(1, totalChars/c.MinChunkChars)
		}
	}

	// Calculate target chunk size
	targetChunkChars := totalChars / optimalChunks
	overlapChars := max(200, targetChunkChars/10) // 10% overlap, min 200 chars

	// Try to split on PAGE BREAK markers first
	pageSections := strings.Split(text, "\n\n=== PAGE BREAK ===\n\n")

	if len(pageSections) > 1 {
		return c.chunkByPages(pageSections, targetChunkChars, overlapChars, lines)
	}

	return c.chunkByCharacters(text, targetChunkChars, overlapChars, lines)
}

// chunkByPages chunks document using PAGE BREAK markers as semantic boundaries
func (c *Chunker) chunkByPages(pageSections []string, targetChunkChars, overlapChars int, allLines []string) []models.ChunkInfo {
	var chunks []models.ChunkInfo
	chunkID := 0
	var currentChunkPages []string
	currentChunkSize := 0

	for _, pageContent := range pageSections {
		pageSize := len(pageContent)

		// Add page to current chunk if it fits
		if currentChunkSize == 0 || (currentChunkSize+pageSize) < targetChunkChars*3/2 {
			currentChunkPages = append(currentChunkPages, pageContent)
			currentChunkSize += pageSize
		} else {
			// Current chunk is large enough, save it
			chunkText := strings.Join(currentChunkPages, "\n\n=== PAGE BREAK ===\n\n")
			startLine, endLine := c.findLineNumbers(chunkText, allLines, chunkID)
			chunks = append(chunks, models.ChunkInfo{
				ChunkID:   formatChunkID(chunkID),
				Text:      chunkText,
				LineStart: startLine,
				LineEnd:   endLine,
			})

			// Start new chunk with overlap from last page
			if overlapChars > 0 && len(currentChunkPages) > 0 {
				lastPage := currentChunkPages[len(currentChunkPages)-1]
				currentChunkPages = []string{lastPage, pageContent}
				currentChunkSize = len(lastPage) + pageSize
			} else {
				currentChunkPages = []string{pageContent}
				currentChunkSize = pageSize
			}

			chunkID++
		}
	}

	// Don't forget the last chunk
	if len(currentChunkPages) > 0 {
		chunkText := strings.Join(currentChunkPages, "\n\n=== PAGE BREAK ===\n\n")
		startLine, endLine := c.findLineNumbers(chunkText, allLines, chunkID)
		chunks = append(chunks, models.ChunkInfo{
			ChunkID:   formatChunkID(chunkID),
			Text:      chunkText,
			LineStart: startLine,
			LineEnd:   endLine,
		})
	}

	return chunks
}

// chunkByCharacters chunks document by character count with paragraph awareness
func (c *Chunker) chunkByCharacters(text string, targetChunkChars, overlapChars int, allLines []string) []models.ChunkInfo {
	var chunks []models.ChunkInfo
	chunkID := 0
	position := 0
	textLength := len(text)

	for position < textLength {
		// Calculate chunk end position
		chunkEnd := min(position+targetChunkChars, textLength)

		// Try to break at paragraph boundary
		if chunkEnd < textLength {
			searchStart := max(position, chunkEnd-500)
			searchEnd := min(textLength, chunkEnd+500)
			searchRegion := text[searchStart:searchEnd]

			// Look for paragraph break (double newline)
			paraBreak := strings.Index(searchRegion, "\n\n")
			if paraBreak != -1 {
				chunkEnd = searchStart + paraBreak + 2
			} else {
				// No paragraph break, try single newline
				halfRegion := len(searchRegion) / 2
				newline := strings.Index(searchRegion[halfRegion:], "\n")
				if newline != -1 {
					chunkEnd = searchStart + halfRegion + newline + 1
				}
			}
		}

		// Extract chunk
		chunkText := text[position:chunkEnd]
		startLine, endLine := c.findLineNumbers(chunkText, allLines, chunkID)

		chunks = append(chunks, models.ChunkInfo{
			ChunkID:   formatChunkID(chunkID),
			Text:      chunkText,
			LineStart: startLine,
			LineEnd:   endLine,
			CharStart: position,
			CharEnd:   chunkEnd,
		})

		chunkID++

		// Break if we've reached the end of the text
		if chunkEnd >= textLength {
			break
		}

		// Move forward with overlap
		position = chunkEnd - overlapChars

		// Safety check: ensure we're making progress
		if position <= 0 {
			break
		}
	}

	return chunks
}

// findLineNumbers finds accurate line numbers for a chunk using fingerprint matching
func (c *Chunker) findLineNumbers(chunkText string, allLines []string, chunkID int) (int, int) {
	chunkLines := strings.Split(chunkText, "\n")
	chunkLineCount := len(chunkLines)

	// For first chunk, start at line 1
	if chunkID == 0 {
		return 1, chunkLineCount
	}

	// Build fingerprint from first non-empty lines
	var chunkFingerprint []string
	emptyLinesBeforeFingerprint := 0

	for i := 0; i < min(15, len(chunkLines)); i++ {
		stripped := strings.TrimSpace(chunkLines[i])
		if stripped != "" {
			chunkFingerprint = append(chunkFingerprint, stripped)
			if len(chunkFingerprint) >= 5 {
				break
			}
		} else if len(chunkFingerprint) == 0 {
			emptyLinesBeforeFingerprint++
		}
	}

	if len(chunkFingerprint) == 0 {
		// Fallback for empty chunks
		estimatedStart := chunkID*50 + 1
		return estimatedStart, min(estimatedStart+chunkLineCount, len(allLines))
	}

	// Search for fingerprint in document
	var docFingerprint []string
	fingerprintStartIdx := -1

	for idx := 0; idx < len(allLines); idx++ {
		stripped := strings.TrimSpace(allLines[idx])
		if stripped == "" {
			continue
		}

		if len(docFingerprint) == 0 {
			if stripped == chunkFingerprint[0] {
				fingerprintStartIdx = idx
				docFingerprint = append(docFingerprint, stripped)
			}
		} else {
			if len(docFingerprint) < len(chunkFingerprint) && stripped == chunkFingerprint[len(docFingerprint)] {
				docFingerprint = append(docFingerprint, stripped)
			} else if stripped != chunkFingerprint[len(docFingerprint)] {
				// Reset and check if current line matches first fingerprint line
				docFingerprint = nil
				fingerprintStartIdx = -1
				if stripped == chunkFingerprint[0] {
					fingerprintStartIdx = idx
					docFingerprint = append(docFingerprint, stripped)
				}
			}
		}

		// Found complete match
		if len(docFingerprint) == len(chunkFingerprint) {
			actualStartIdx := fingerprintStartIdx - emptyLinesBeforeFingerprint
			if actualStartIdx < 0 {
				actualStartIdx = 0
			}
			startLine := actualStartIdx + 1
			endLine := min(startLine+chunkLineCount-1, len(allLines))
			return startLine, endLine
		}
	}

	// Fallback estimate
	estimatedStart := chunkID*50 + 1
	return estimatedStart, min(estimatedStart+chunkLineCount, len(allLines))
}

// legacyChunkText implements line-based chunking for backward compatibility
func (c *Chunker) legacyChunkText(text string) []models.ChunkInfo {
	lines := strings.Split(text, "\n")
	var chunks []models.ChunkInfo
	chunkID := 0
	start := 0

	for start < len(lines) {
		end := min(start+c.ChunkSize, len(lines))
		chunkLines := lines[start:end]
		chunkText := strings.Join(chunkLines, "\n")

		chunks = append(chunks, models.ChunkInfo{
			ChunkID:   formatChunkID(chunkID),
			Text:      chunkText,
			LineStart: start + 1, // 1-indexed
			LineEnd:   end,
		})

		chunkID++
		start += c.ChunkSize - c.OverlapSize

		if end >= len(lines) {
			break
		}
	}

	return chunks
}

func formatChunkID(id int) string {
	return "chunk_" + padLeft(id, 4)
}

func padLeft(n, width int) string {
	s := ""
	for i := 0; i < width; i++ {
		s += "0"
	}
	ns := s + itoa(n)
	return ns[len(ns)-width:]
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var digits []byte
	for n > 0 {
		digits = append([]byte{byte('0' + n%10)}, digits...)
		n /= 10
	}
	return string(digits)
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
