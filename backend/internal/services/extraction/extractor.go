package extraction

import (
	"context"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
	"sync"

	"github.com/nesposito/frfr/internal/domain/models"
	"github.com/nesposito/frfr/internal/services/claude"
)

// Extractor handles fact extraction from document chunks
type Extractor struct {
	client     *claude.Client
	chunker    *Chunker
	patterns   *ExtractionPatterns
	maxWorkers int
	maxRetries int
}

// NewExtractor creates a new fact extractor
func NewExtractor(client *claude.Client, maxWorkers int) *Extractor {
	return &Extractor{
		client:     client,
		chunker:    NewChunker(),
		patterns:   &ExtractionPatterns{},
		maxWorkers: maxWorkers,
		maxRetries: 3,
	}
}

// ExtractionProgress reports progress during extraction
type ExtractionProgress struct {
	Document       string
	ChunkID        string
	ChunksTotal    int
	ChunksComplete int
	FactsExtracted int
	Message        string
	Error          error
}

// SummarizeDocument generates a structured summary of the document
func (e *Extractor) SummarizeDocument(ctx context.Context, text, documentName string) (*models.DocumentSummary, error) {
	prompt := buildSummaryPrompt(text, documentName)

	response, err := e.client.Prompt(ctx, prompt, &claude.PromptOptions{
		MaxTokens: 4096,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to generate summary: %w", err)
	}

	// Parse JSON from response
	summary, err := parseSummaryResponse(response)
	if err != nil {
		return nil, fmt.Errorf("failed to parse summary: %w", err)
	}

	return summary, nil
}

// ExtractFacts extracts facts from all chunks with parallel processing
func (e *Extractor) ExtractFacts(
	ctx context.Context,
	text string,
	documentName string,
	summary *models.DocumentSummary,
	progressChan chan<- ExtractionProgress,
) ([]models.FactExtractionResult, error) {
	// Chunk the text
	chunks := e.chunker.ChunkText(text)

	if progressChan != nil {
		progressChan <- ExtractionProgress{
			Document:    documentName,
			ChunksTotal: len(chunks),
			Message:     fmt.Sprintf("Split document into %d chunks", len(chunks)),
		}
	}

	// Create worker pool
	type workItem struct {
		chunk models.ChunkInfo
		index int
	}

	workChan := make(chan workItem, len(chunks))
	resultChan := make(chan models.FactExtractionResult, len(chunks))
	errorChan := make(chan error, len(chunks))

	// Start workers
	var wg sync.WaitGroup
	for i := 0; i < e.maxWorkers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for item := range workChan {
				result, err := e.extractFactsFromChunk(ctx, item.chunk, documentName, summary)
				if err != nil {
					errorChan <- fmt.Errorf("chunk %s: %w", item.chunk.ChunkID, err)
					continue
				}
				resultChan <- *result

				if progressChan != nil {
					progressChan <- ExtractionProgress{
						Document:       documentName,
						ChunkID:        item.chunk.ChunkID,
						FactsExtracted: len(result.Facts),
						Message:        fmt.Sprintf("Extracted %d facts from %s", len(result.Facts), item.chunk.ChunkID),
					}
				}
			}
		}()
	}

	// Send work
	for i, chunk := range chunks {
		workChan <- workItem{chunk: chunk, index: i}
	}
	close(workChan)

	// Wait for completion
	go func() {
		wg.Wait()
		close(resultChan)
		close(errorChan)
	}()

	// Collect results
	var results []models.FactExtractionResult
	var errors []error

	for result := range resultChan {
		results = append(results, result)
	}
	for err := range errorChan {
		errors = append(errors, err)
	}

	if len(errors) > 0 && len(results) == 0 {
		return nil, fmt.Errorf("all extractions failed: %v", errors[0])
	}

	return results, nil
}

// extractFactsFromChunk extracts facts from a single chunk with retries
func (e *Extractor) extractFactsFromChunk(
	ctx context.Context,
	chunk models.ChunkInfo,
	documentName string,
	summary *models.DocumentSummary,
) (*models.FactExtractionResult, error) {
	// Pre-parse chunk for guidance
	preParsed := e.preParseChunk(chunk.Text)

	// Try with progressively smaller max_tokens on failure
	maxTokensOptions := []int{6000, 4000, 2000, 1000}

	var lastErr error
	for _, maxTokens := range maxTokensOptions {
		prompt := buildExtractionPrompt(chunk, documentName, summary, preParsed)

		response, err := e.client.Prompt(ctx, prompt, &claude.PromptOptions{
			MaxTokens: maxTokens,
		})
		if err != nil {
			lastErr = err
			continue
		}

		facts, err := parseFactsResponse(response, documentName, chunk)
		if err != nil {
			lastErr = err
			continue
		}

		// Post-process facts
		facts = e.postProcessFacts(facts, chunk.Text)

		return &models.FactExtractionResult{
			ChunkID:   chunk.ChunkID,
			Document:  documentName,
			Facts:     facts,
			LineStart: chunk.LineStart,
			LineEnd:   chunk.LineEnd,
		}, nil
	}

	return nil, fmt.Errorf("extraction failed after retries: %w", lastErr)
}

// PreParsedChunk contains rule-based pre-extraction results
type PreParsedChunk struct {
	QuantitativeValues []QuantitativeValue
	EncryptionSpecs    []string
	AuthSpecs          []string
	NetworkSpecs       []string
	Roles              []string
}

// preParseChunk extracts structured data using regex patterns
func (e *Extractor) preParseChunk(text string) *PreParsedChunk {
	return &PreParsedChunk{
		QuantitativeValues: e.patterns.ExtractAllQuantitative(text),
		EncryptionSpecs:    e.patterns.ExtractEncryptionSpecs(text),
		AuthSpecs:          e.patterns.ExtractAuthenticationSpecs(text),
		NetworkSpecs:       e.patterns.ExtractNetworkSpecs(text),
		Roles:              e.patterns.ExtractRoles(text),
	}
}

// postProcessFacts enriches and filters facts
func (e *Extractor) postProcessFacts(facts []models.ExtractedFact, chunkText string) []models.ExtractedFact {
	var processed []models.ExtractedFact

	for _, fact := range facts {
		// Normalize evidence format
		fact.NormalizeEvidence()

		// Recalculate specificity score
		fact.SpecificityScore = CalculateSpecificityScore(
			fact.Claim,
			fact.QuantitativeValues,
			fact.Entities,
			fact.ProcessDetails,
		)

		// Filter out test-only facts if they're too generic
		if fact.FactType == "test_result" && fact.SpecificityScore < 0.3 {
			continue
		}

		processed = append(processed, fact)
	}

	return processed
}

// buildSummaryPrompt creates the prompt for document summarization
func buildSummaryPrompt(text, documentName string) string {
	// Use first ~10000 chars for summary
	sampleText := text
	if len(text) > 10000 {
		sampleText = text[:10000] + "\n\n[... document continues ...]"
	}

	return fmt.Sprintf(`Analyze this document and provide a structured summary in JSON format.

Document: %s

Sample text:
%s

Respond with ONLY a JSON object (no markdown, no explanation) with this structure:
{
  "document_type": "SOC2_Type2|pentest|architecture|policy|other",
  "structural_pattern": "claim-based|findings-based|procedural|narrative",
  "section_types": [
    {"name": "section name", "extraction_priority": "high|medium|low", "description": "what this section contains"}
  ],
  "major_headings": ["list", "of", "major", "section", "headings"],
  "fact_density_pattern": "description of where facts are concentrated",
  "extraction_guidance": "specific guidance for extracting facts from this document type",
  "key_entities": ["important", "named", "entities", "found"],
  "overview": "1-2 sentence overview of the document"
}`, documentName, sampleText)
}

// buildExtractionPrompt creates the prompt for fact extraction
func buildExtractionPrompt(chunk models.ChunkInfo, documentName string, summary *models.DocumentSummary, preParsed *PreParsedChunk) string {
	var sb strings.Builder

	sb.WriteString("Extract ALL factual claims from this document chunk. Be AGGRESSIVE - extract every specific, verifiable fact.\n\n")

	// Add document context
	if summary != nil {
		sb.WriteString(fmt.Sprintf("Document type: %s\n", summary.DocumentType))
		sb.WriteString(fmt.Sprintf("Extraction guidance: %s\n\n", summary.ExtractionGuidance))
	}

	// Add pre-parsed guidance
	if preParsed != nil && len(preParsed.QuantitativeValues) > 0 {
		sb.WriteString("IMPORTANT: The following quantitative values were detected - ensure you extract facts containing these:\n")
		for _, qv := range preParsed.QuantitativeValues {
			sb.WriteString(fmt.Sprintf("  - %s (%s)\n", qv.Value, qv.Type))
		}
		sb.WriteString("\n")
	}

	// Add chunk info
	sb.WriteString(fmt.Sprintf("Source: %s, Lines %d-%d\n\n", documentName, chunk.LineStart, chunk.LineEnd))

	// Add the chunk text
	sb.WriteString("CHUNK TEXT:\n")
	sb.WriteString(chunk.Text)
	sb.WriteString("\n\n")

	// Add extraction instructions
	sb.WriteString(`INSTRUCTIONS:
1. Extract EVERY factual claim - be aggressive, not conservative
2. Each fact must have an EXACT quote from the text as evidence
3. Classify each fact by type and control family
4. Include ALL quantitative values (percentages, frequencies, durations, counts)
5. Extract WHO performs actions, WHEN they occur, and HOW

Respond with ONLY a JSON array of facts (no markdown, no explanation):
[
  {
    "claim": "The specific factual assertion",
    "source_doc": "document name",
    "source_location": "Lines X-Y",
    "evidence_quotes": [
      {"quote": "EXACT text from document", "source_location": "Lines X-Y", "relevance": "why this supports the claim"}
    ],
    "confidence": 0.95,
    "fact_type": "technical_control|organizational|process|metric|CUEC|test_result|architecture|compliance",
    "control_family": "access_control|encryption|monitoring|backup_recovery|change_management|incident_response",
    "specificity_score": 0.8,
    "entities": ["named", "entities"],
    "quantitative_values": ["90 days", "99.9%"],
    "process_details": {"who": "role", "when": "frequency", "how": "method"},
    "section_context": "section name",
    "related_control_ids": ["CC6.1", "A.1.2"]
  }
]`)

	return sb.String()
}

// parseSummaryResponse parses the summary JSON response
func parseSummaryResponse(response string) (*models.DocumentSummary, error) {
	// Clean up response - remove markdown if present
	response = cleanJSONResponse(response)

	var summary models.DocumentSummary
	if err := json.Unmarshal([]byte(response), &summary); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}

	return &summary, nil
}

// parseFactsResponse parses the facts JSON response
func parseFactsResponse(response, documentName string, chunk models.ChunkInfo) ([]models.ExtractedFact, error) {
	// Clean up response
	response = cleanJSONResponse(response)

	var rawFacts []map[string]interface{}
	if err := json.Unmarshal([]byte(response), &rawFacts); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}

	var facts []models.ExtractedFact
	for _, raw := range rawFacts {
		fact := models.ExtractedFact{
			SourceDoc:      documentName,
			SourceLocation: fmt.Sprintf("Lines %d-%d", chunk.LineStart, chunk.LineEnd),
		}

		// Extract fields
		if v, ok := raw["claim"].(string); ok {
			fact.Claim = v
		}
		if v, ok := raw["source_location"].(string); ok {
			fact.SourceLocation = v
		}
		if v, ok := raw["confidence"].(float64); ok {
			fact.Confidence = v
		} else {
			fact.Confidence = 0.8 // Default
		}
		if v, ok := raw["fact_type"].(string); ok {
			fact.FactType = v
		}
		if v, ok := raw["control_family"].(string); ok {
			fact.ControlFamily = v
		}
		if v, ok := raw["specificity_score"].(float64); ok {
			fact.SpecificityScore = v
		}
		if v, ok := raw["section_context"].(string); ok {
			fact.SectionContext = v
		}

		// Handle evidence quotes (V5 format)
		if eqs, ok := raw["evidence_quotes"].([]interface{}); ok {
			for _, eq := range eqs {
				if eqMap, ok := eq.(map[string]interface{}); ok {
					quote := models.EvidenceQuote{}
					if v, ok := eqMap["quote"].(string); ok {
						quote.Quote = v
					}
					if v, ok := eqMap["source_location"].(string); ok {
						quote.SourceLocation = v
					}
					if v, ok := eqMap["relevance"].(string); ok {
						quote.Relevance = v
					}
					fact.EvidenceQuotes = append(fact.EvidenceQuotes, quote)
				}
			}
		}
		// Fallback to V4 format
		if v, ok := raw["evidence_quote"].(string); ok && len(fact.EvidenceQuotes) == 0 {
			fact.EvidenceQuote = v
		}

		// Handle arrays
		if v, ok := raw["entities"].([]interface{}); ok {
			for _, e := range v {
				if s, ok := e.(string); ok {
					fact.Entities = append(fact.Entities, s)
				}
			}
		}
		if v, ok := raw["quantitative_values"].([]interface{}); ok {
			for _, e := range v {
				if s, ok := e.(string); ok {
					fact.QuantitativeValues = append(fact.QuantitativeValues, s)
				}
			}
		}
		if v, ok := raw["related_control_ids"].([]interface{}); ok {
			for _, e := range v {
				if s, ok := e.(string); ok {
					fact.RelatedControlIDs = append(fact.RelatedControlIDs, s)
				}
			}
		}

		// Handle process details
		if pd, ok := raw["process_details"].(map[string]interface{}); ok {
			fact.ProcessDetails = make(map[string]string)
			for k, v := range pd {
				if s, ok := v.(string); ok {
					fact.ProcessDetails[k] = s
				}
			}
		}

		if fact.Claim != "" {
			facts = append(facts, fact)
		}
	}

	return facts, nil
}

// cleanJSONResponse removes markdown code blocks and extra whitespace
func cleanJSONResponse(response string) string {
	// Remove markdown code blocks
	re := regexp.MustCompile("```(?:json)?\\s*")
	response = re.ReplaceAllString(response, "")
	response = strings.ReplaceAll(response, "```", "")

	// Trim whitespace
	response = strings.TrimSpace(response)

	return response
}
