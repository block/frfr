package query

import (
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

	"github.com/nesposito/frfr/internal/domain/models"
)

// ChunkManager manages text chunks for context retrieval during queries
type ChunkManager struct {
	sessionDir string
	chunks     map[string]models.ChunkInfo // chunkKey -> ChunkInfo
}

// NewChunkManager creates a new chunk manager for a session
func NewChunkManager(sessionDir string) *ChunkManager {
	return &ChunkManager{
		sessionDir: sessionDir,
		chunks:     make(map[string]models.ChunkInfo),
	}
}

// LoadChunks loads all chunks for the session
func (m *ChunkManager) LoadChunks() error {
	chunksDir := filepath.Join(m.sessionDir, "chunks")

	entries, err := os.ReadDir(chunksDir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		return err
	}

	for _, entry := range entries {
		if !strings.HasSuffix(entry.Name(), ".txt") {
			continue
		}

		// Parse filename: document_chunk_XXXX.txt
		name := strings.TrimSuffix(entry.Name(), ".txt")
		parts := strings.Split(name, "_chunk_")
		if len(parts) != 2 {
			continue
		}

		docName := parts[0]
		chunkID := "chunk_" + parts[1]

		// Read chunk text
		text, err := os.ReadFile(filepath.Join(chunksDir, entry.Name()))
		if err != nil {
			continue
		}

		key := docName + ":" + chunkID
		m.chunks[key] = models.ChunkInfo{
			ChunkID:  chunkID,
			Document: docName,
			Text:     string(text),
		}
	}

	return nil
}

// GetChunk retrieves a specific chunk
func (m *ChunkManager) GetChunk(document, chunkID string) *models.ChunkInfo {
	key := document + ":" + chunkID
	if chunk, ok := m.chunks[key]; ok {
		return &chunk
	}
	return nil
}

// FindQuoteInAnyChunk searches all chunks for a quote and returns the chunk key if found
func (m *ChunkManager) FindQuoteInAnyChunk(quote string) string {
	if quote == "" {
		return ""
	}
	for key, chunk := range m.chunks {
		if strings.Contains(chunk.Text, quote) {
			return key
		}
	}
	// Try normalized search
	normalizedQuote := normalizeWS(quote)
	for key, chunk := range m.chunks {
		normalizedText := normalizeWS(chunk.Text)
		if strings.Contains(normalizedText, normalizedQuote) {
			return key + " (normalized)"
		}
	}
	return ""
}

// FindChunkContainingQuote searches all chunks for a quote and returns the chunk
func (m *ChunkManager) FindChunkContainingQuote(document, quote string) *models.ChunkInfo {
	if quote == "" {
		return nil
	}

	// First try exact match
	for _, chunk := range m.chunks {
		if chunk.Document == document && strings.Contains(chunk.Text, quote) {
			return &chunk
		}
	}

	// Try normalized whitespace match
	normalizedQuote := normalizeWS(quote)
	for _, chunk := range m.chunks {
		if chunk.Document == document {
			normalizedText := normalizeWS(chunk.Text)
			if strings.Contains(normalizedText, normalizedQuote) {
				return &chunk
			}
		}
	}

	// Try matching key phrases from the quote (handles interleaved PDF table text)
	// Extract distinctive phrases (skip common words at start)
	if len(quote) > 30 {
		phrases := extractDistinctivePhrases(quote)
		for _, phrase := range phrases {
			if len(phrase) < 15 {
				continue // Skip short phrases
			}
			for _, chunk := range m.chunks {
				if chunk.Document == document {
					// Try both exact and normalized
					if strings.Contains(chunk.Text, phrase) || strings.Contains(normalizeWS(chunk.Text), normalizeWS(phrase)) {
						return &chunk
					}
				}
			}
		}
	}

	return nil
}

// extractDistinctivePhrases extracts meaningful phrases from a quote
// Skips common prefixes like "The company" and looks for specific content
func extractDistinctivePhrases(quote string) []string {
	var phrases []string

	// Common SOC2 prefixes to skip
	skipPrefixes := []string{
		"The company ",
		"the company ",
		"Inspected the ",
		"inspected the ",
	}

	working := quote
	for _, prefix := range skipPrefixes {
		if strings.HasPrefix(working, prefix) {
			working = working[len(prefix):]
			break
		}
	}

	// Take first substantial portion after skipping prefix
	if len(working) > 20 {
		// Find a good break point (after 20+ chars, at a space)
		breakPoint := 40
		if breakPoint > len(working) {
			breakPoint = len(working)
		}
		for i := breakPoint; i > 20; i-- {
			if working[i-1] == ' ' {
				breakPoint = i - 1
				break
			}
		}
		phrases = append(phrases, working[:breakPoint])
	}

	// Also try middle portion of the original quote
	if len(quote) > 60 {
		mid := len(quote) / 3
		end := mid + 30
		if end > len(quote) {
			end = len(quote)
		}
		// Find word boundaries
		for mid > 0 && quote[mid] != ' ' {
			mid++
		}
		mid++ // skip space
		for end < len(quote) && quote[end] != ' ' {
			end++
		}
		if end > mid+15 {
			phrases = append(phrases, quote[mid:end])
		}
	}

	return phrases
}

func normalizeWS(s string) string {
	var result strings.Builder
	inWS := false
	for _, r := range s {
		if r == ' ' || r == '\n' || r == '\r' || r == '\t' {
			if !inWS {
				result.WriteRune(' ')
				inWS = true
			}
		} else {
			result.WriteRune(r)
			inWS = false
		}
	}
	return result.String()
}

// FindChunkForLocation finds the chunk containing a specific location
func (m *ChunkManager) FindChunkForLocation(document, location string) *models.ChunkInfo {
	// Extract chunk ID from location if present
	chunkIDMatch := regexp.MustCompile(`chunk_\d+`).FindString(location)
	if chunkIDMatch != "" {
		return m.GetChunk(document, chunkIDMatch)
	}

	// Extract line numbers and search
	startLine, _ := parseLineNumbers(location)
	if startLine > 0 {
		// Find chunk containing this line
		for _, chunk := range m.chunks {
			if chunk.Document == document {
				if startLine >= chunk.LineStart && startLine <= chunk.LineEnd {
					return &chunk
				}
			}
		}
	}

	return nil
}

// ChunkWithEvidence associates a chunk with its evidence facts
type ChunkWithEvidence struct {
	Chunk models.ChunkInfo
	Facts []models.ExtractedFact
}

// GetEvidenceChunks retrieves chunks containing evidence for the given facts
func (m *ChunkManager) GetEvidenceChunks(facts []models.ExtractedFact) []ChunkWithEvidence {
	chunkFacts := make(map[string][]models.ExtractedFact)

	for _, fact := range facts {
		chunk := m.FindChunkForLocation(fact.SourceDoc, fact.SourceLocation)
		if chunk != nil {
			key := chunk.Document + ":" + chunk.ChunkID
			chunkFacts[key] = append(chunkFacts[key], fact)
		}
	}

	var results []ChunkWithEvidence
	for key, factList := range chunkFacts {
		if chunk, ok := m.chunks[key]; ok {
			results = append(results, ChunkWithEvidence{
				Chunk: chunk,
				Facts: factList,
			})
		}
	}

	return results
}

// LoadFactsForContext loads facts and returns them with chunk context
func (m *ChunkManager) LoadFactsForContext(factsDir string) ([]models.ExtractedFact, error) {
	entries, err := os.ReadDir(factsDir)
	if err != nil {
		return nil, err
	}

	var allFacts []models.ExtractedFact
	for _, entry := range entries {
		if !strings.HasSuffix(entry.Name(), ".json") {
			continue
		}

		data, err := os.ReadFile(filepath.Join(factsDir, entry.Name()))
		if err != nil {
			continue
		}

		var facts []models.ExtractedFact
		if err := json.Unmarshal(data, &facts); err != nil {
			continue
		}

		allFacts = append(allFacts, facts...)
	}

	return allFacts, nil
}

// SearchRelevantChunks searches for chunks relevant to a query
func (m *ChunkManager) SearchRelevantChunks(query string, limit int) []models.ChunkInfo {
	queryWords := tokenize(strings.ToLower(query))

	type scoredChunk struct {
		chunk models.ChunkInfo
		score int
	}

	var scored []scoredChunk
	for _, chunk := range m.chunks {
		chunkLower := strings.ToLower(chunk.Text)
		score := 0
		for _, word := range queryWords {
			if len(word) < 3 {
				continue
			}
			// Count occurrences
			score += strings.Count(chunkLower, word)
		}
		if score > 0 {
			scored = append(scored, scoredChunk{chunk: chunk, score: score})
		}
	}

	// Sort by score descending
	for i := 0; i < len(scored); i++ {
		for j := i + 1; j < len(scored); j++ {
			if scored[j].score > scored[i].score {
				scored[i], scored[j] = scored[j], scored[i]
			}
		}
	}

	// Return top chunks
	var results []models.ChunkInfo
	for i := 0; i < len(scored) && i < limit; i++ {
		results = append(results, scored[i].chunk)
	}

	return results
}

func tokenize(text string) []string {
	// Split on whitespace and punctuation
	re := regexp.MustCompile(`[^\w]+`)
	return re.Split(text, -1)
}

func parseLineNumbers(location string) (int, int) {
	re := regexp.MustCompile(`Lines?\s*(\d+)(?:\s*-\s*(\d+))?`)
	matches := re.FindStringSubmatch(location)
	if len(matches) < 2 {
		return 0, 0
	}

	start, _ := strconv.Atoi(matches[1])
	end := start
	if len(matches) > 2 && matches[2] != "" {
		end, _ = strconv.Atoi(matches[2])
	}
	return start, end
}
