package query

import (
	"context"
	"fmt"
	"regexp"
	"strconv"
	"strings"

	"github.com/nesposito/frfr/internal/domain/models"
	"github.com/nesposito/frfr/internal/services/claude"
)

// BatchProgress reports the status of parallel batch processing
type BatchProgress struct {
	Phase        string `json:"phase"` // "selecting" or "answering"
	TotalBatches int    `json:"total_batches"`
	Completed    int    `json:"completed"`
	Running      int    `json:"running"`
	FactsFound   int    `json:"facts_found"`
}

// ProgressCallback is called to report query progress
type ProgressCallback func(BatchProgress)

// ConversationTurn represents a prior question and answer in the conversation
type ConversationTurn struct {
	Query  string
	Answer string
}

// Processor handles query processing using facts and Claude API
type Processor struct {
	client              *claude.Client
	chunkManager        *ChunkManager
	facts               []models.ExtractedFact
	onProgress          ProgressCallback
	conversationHistory []ConversationTurn
}

// SetProgressCallback sets the callback for progress updates
func (p *Processor) SetProgressCallback(cb ProgressCallback) {
	p.onProgress = cb
}

// SetConversationHistory provides prior Q&A turns so follow-up questions can reference earlier context
func (p *Processor) SetConversationHistory(history []ConversationTurn) {
	p.conversationHistory = history
}

// NewProcessor creates a new query processor
func NewProcessor(client *claude.Client, chunkManager *ChunkManager, facts []models.ExtractedFact) *Processor {
	return &Processor{
		client:       client,
		chunkManager: chunkManager,
		facts:        facts,
	}
}

// QueryResult contains the result of a query
type QueryResult struct {
	Query   string         `json:"query"`
	Answer  string         `json:"answer"`
	Sources []SourceResult `json:"sources"`
}

// SourceResult contains evidence for a query answer
type SourceResult struct {
	FactIndex  int     `json:"fact_index"` // Canonical fact number for citation linking
	Claim      string  `json:"claim"`
	Quote      string  `json:"quote"`
	Document   string  `json:"document"`
	Location   string  `json:"location"`
	Confidence float64 `json:"confidence"`
	ChunkText  string  `json:"chunk_text,omitempty"`
}

// ProcessQuery processes a query and returns an answer with sources
func (p *Processor) ProcessQuery(ctx context.Context, query string) (*QueryResult, error) {
	if len(p.facts) == 0 {
		return &QueryResult{
			Query:   query,
			Answer:  "No facts have been extracted from the documents yet.",
			Sources: []SourceResult{},
		}, nil
	}

	// Step 1: Use LLM to select relevant facts
	relevantFacts, err := p.selectRelevantFactsWithLLM(ctx, query)
	if err != nil {
		// Fallback to keyword-based selection if LLM fails
		relevantFacts = p.findRelevantFacts(query)
	}

	if len(relevantFacts) == 0 {
		return &QueryResult{
			Query:   query,
			Answer:  "I couldn't find any relevant information in the documents to answer this question.",
			Sources: []SourceResult{},
		}, nil
	}

	// Step 2: Generate answer using Claude (with citation instructions)
	// Report that we're now in the answering phase
	if p.onProgress != nil {
		p.onProgress(BatchProgress{
			Phase:        "answering",
			TotalBatches: 1,
			Completed:    0,
			Running:      1,
			FactsFound:   len(relevantFacts),
		})
	}

	answer, err := p.generateAnswer(ctx, query, relevantFacts)
	if err != nil {
		// Fallback to simple answer - use all facts
		answer = p.simpleFallbackAnswer(query, relevantFacts)
		sources := p.buildSources(relevantFacts)
		return &QueryResult{
			Query:   query,
			Answer:  answer,
			Sources: sources,
		}, nil
	}

	// Return all relevant facts as sources so citation indices match
	// (citations in answer like [3], [17] refer to relevantFacts indices)
	sources := p.buildSources(relevantFacts)

	return &QueryResult{
		Query:   query,
		Answer:  answer,
		Sources: sources,
	}, nil
}

// SelectRelevantFacts selects facts relevant to the query using LLM with keyword fallback.
func (p *Processor) SelectRelevantFacts(ctx context.Context, query string) ([]models.ExtractedFact, error) {
	facts, err := p.selectRelevantFactsWithLLM(ctx, query)
	if err != nil {
		facts = p.findRelevantFacts(query)
	}
	return facts, nil
}

// SimpleFallbackAnswer generates a simple answer without Claude
func (p *Processor) SimpleFallbackAnswer(query string, facts []models.ExtractedFact) string {
	return p.simpleFallbackAnswer(query, facts)
}

// BuildSources builds source results from facts
func (p *Processor) BuildSources(facts []models.ExtractedFact) []SourceResult {
	return p.buildSources(facts)
}

// selectRelevantFactsWithLLM uses Claude to identify which facts are relevant to the query.
// For large fact sets, it splits into batches and processes them in parallel.
func (p *Processor) selectRelevantFactsWithLLM(ctx context.Context, query string) ([]models.ExtractedFact, error) {
	if p.client == nil {
		return nil, fmt.Errorf("no Claude client available")
	}

	const batchSize = 150 // Facts per batch - balances token limits with parallelism
	numFacts := len(p.facts)

	if numFacts == 0 {
		return nil, nil
	}

	// Calculate number of batches needed
	numBatches := (numFacts + batchSize - 1) / batchSize

	// Report initial progress
	if p.onProgress != nil {
		p.onProgress(BatchProgress{
			Phase:        "selecting",
			TotalBatches: numBatches,
			Completed:    0,
			Running:      numBatches,
			FactsFound:   0,
		})
	}

	// Channel to collect results from parallel workers
	type batchResult struct {
		indices []int
		err     error
	}
	results := make(chan batchResult, numBatches)

	// Launch parallel workers for each batch
	for batch := 0; batch < numBatches; batch++ {
		startIdx := batch * batchSize
		endIdx := startIdx + batchSize
		if endIdx > numFacts {
			endIdx = numFacts
		}

		go func(batchNum, start, end int) {
			indices, err := p.evaluateFactBatch(ctx, query, start, end)
			results <- batchResult{indices: indices, err: err}
		}(batch, startIdx, endIdx)
	}

	// Collect results from all batches, deduplicating as we go
	seen := make(map[int]bool)
	var uniqueIndices []int
	var firstErr error
	completed := 0

	for i := 0; i < numBatches; i++ {
		result := <-results
		completed++
		if result.err != nil && firstErr == nil {
			firstErr = result.err
		} else {
			// Deduplicate as we collect
			for _, idx := range result.indices {
				if !seen[idx] {
					seen[idx] = true
					uniqueIndices = append(uniqueIndices, idx)
				}
			}
		}

		// Report progress after each batch completes (with deduplicated count)
		if p.onProgress != nil {
			p.onProgress(BatchProgress{
				Phase:        "selecting",
				TotalBatches: numBatches,
				Completed:    completed,
				Running:      numBatches - completed,
				FactsFound:   len(uniqueIndices),
			})
		}
	}

	// If all batches failed, return the error
	if len(uniqueIndices) == 0 && firstErr != nil {
		return nil, firstErr
	}

	// Sort to maintain document order
	for i := 0; i < len(uniqueIndices); i++ {
		for j := i + 1; j < len(uniqueIndices); j++ {
			if uniqueIndices[j] < uniqueIndices[i] {
				uniqueIndices[i], uniqueIndices[j] = uniqueIndices[j], uniqueIndices[i]
			}
		}
	}

	var relevantFacts []models.ExtractedFact
	for _, idx := range uniqueIndices {
		if idx >= 0 && idx < numFacts {
			relevantFacts = append(relevantFacts, p.facts[idx])
		}
	}

	return relevantFacts, nil
}

// evaluateFactBatch sends a batch of facts to Claude and returns relevant indices (0-indexed into p.facts)
func (p *Processor) evaluateFactBatch(ctx context.Context, query string, startIdx, endIdx int) ([]int, error) {
	var sb strings.Builder
	sb.WriteString("You are analyzing extracted facts from compliance/audit documents to find ones relevant to a user's question.\n\n")

	// Include conversation history so follow-up questions can be understood in context
	if len(p.conversationHistory) > 0 {
		sb.WriteString("Conversation so far:\n")
		for _, turn := range p.conversationHistory {
			sb.WriteString(fmt.Sprintf("User: %s\n", turn.Query))
			// Include a truncated answer to keep the prompt reasonable
			answer := turn.Answer
			if len(answer) > 300 {
				answer = answer[:300] + "..."
			}
			sb.WriteString(fmt.Sprintf("Assistant: %s\n\n", answer))
		}
	}

	sb.WriteString(fmt.Sprintf("Question: %s\n\n", query))
	sb.WriteString("Think broadly about relevance. For example:\n")
	sb.WriteString("- Questions about 'employee onboarding' relate to: hiring, background checks, training, orientation, access provisioning\n")
	sb.WriteString("- Questions about 'security controls' relate to: encryption, access control, authentication, monitoring, policies\n")
	sb.WriteString("- Questions about 'data protection' relate to: classification, encryption, privacy, handling procedures\n\n")
	sb.WriteString("Facts:\n")

	// Number facts locally within batch (1-indexed for Claude)
	for i := startIdx; i < endIdx; i++ {
		localIdx := i - startIdx + 1 // 1, 2, 3, ...
		sb.WriteString(fmt.Sprintf("[%d] %s\n", localIdx, p.facts[i].Claim))
	}

	sb.WriteString("\nReturn the numbers of ALL facts that could help answer the question, even if only partially relevant.\n")
	sb.WriteString("Format: comma-separated numbers (e.g., 3, 7, 12, 15)\n")
	sb.WriteString("If no facts in this batch are relevant, respond with: NONE\n")
	sb.WriteString("\nRelevant fact numbers:")

	response, err := p.client.Prompt(ctx, sb.String(), &claude.PromptOptions{
		MaxTokens: 500,
	})
	if err != nil {
		return nil, err
	}

	// Parse the response to get fact indices
	response = strings.TrimSpace(response)
	if strings.ToUpper(response) == "NONE" || response == "" {
		return nil, nil
	}

	// Extract numbers from the response
	numRe := regexp.MustCompile(`\d+`)
	numStrs := numRe.FindAllString(response, -1)

	var indices []int
	for _, numStr := range numStrs {
		localIdx, err := strconv.Atoi(numStr)
		if err != nil {
			continue
		}
		// Convert 1-indexed local to 0-indexed global
		globalIdx := startIdx + localIdx - 1
		// Validate it's within this batch's range
		if globalIdx >= startIdx && globalIdx < endIdx {
			indices = append(indices, globalIdx)
		}
	}

	return indices, nil
}

// parseCitations extracts fact numbers cited in the answer (e.g., [1], [2, 5], [1, 4, 9])
func (p *Processor) parseCitations(answer string) []int {
	var cited []int
	seen := make(map[int]bool)

	// Match bracket contents: [1], [2, 5], [1, 4, 9], etc.
	re := regexp.MustCompile(`\[([^\]]+)\]`)
	matches := re.FindAllStringSubmatch(answer, -1)

	// Extract all numbers from each bracket
	numRe := regexp.MustCompile(`\d+`)

	for _, match := range matches {
		if len(match) >= 2 {
			// Find all numbers within this bracket
			nums := numRe.FindAllString(match[1], -1)
			for _, numStr := range nums {
				if num, err := strconv.Atoi(numStr); err == nil && !seen[num] {
					cited = append(cited, num)
					seen[num] = true
				}
			}
		}
	}

	return cited
}

// findRelevantFacts finds facts relevant to the query
func (p *Processor) findRelevantFacts(query string) []models.ExtractedFact {
	queryLower := strings.ToLower(query)
	queryWords := tokenize(queryLower)

	// Filter out common stop words
	stopWords := map[string]bool{
		"the": true, "a": true, "an": true, "and": true, "or": true, "but": true,
		"in": true, "on": true, "at": true, "to": true, "for": true, "of": true,
		"with": true, "by": true, "from": true, "is": true, "are": true, "was": true,
		"were": true, "been": true, "be": true, "have": true, "has": true, "had": true,
		"do": true, "does": true, "did": true, "will": true, "would": true, "could": true,
		"should": true, "may": true, "might": true, "must": true, "can": true,
		"this": true, "that": true, "these": true, "those": true, "what": true,
		"which": true, "who": true, "whom": true, "how": true, "when": true, "where": true,
		"why": true, "all": true, "each": true, "every": true, "any": true, "some": true,
	}

	var significantWords []string
	for _, word := range queryWords {
		if len(word) >= 3 && !stopWords[word] {
			significantWords = append(significantWords, word)
		}
	}

	type scoredFact struct {
		fact  models.ExtractedFact
		score float64
	}

	var scored []scoredFact
	for _, fact := range p.facts {
		score := 0.0

		// Build searchable text from all relevant fields
		claimLower := strings.ToLower(fact.Claim)

		// Get evidence text
		var evidenceText string
		if quote := fact.GetPrimaryQuote(); quote != "" {
			evidenceText = strings.ToLower(quote)
		}

		// Build full searchable text
		searchParts := []string{
			claimLower,
			evidenceText,
			strings.ToLower(strings.Join(fact.Entities, " ")),
			strings.ToLower(fact.FactType),
			strings.ToLower(fact.ControlFamily),
			strings.ToLower(fact.SectionContext),
		}
		fullText := strings.Join(searchParts, " ")

		// Check for full query phrase match (highest value)
		if strings.Contains(claimLower, queryLower) {
			score += 10.0
		} else if strings.Contains(fullText, queryLower) {
			score += 5.0
		}

		// Score individual word matches
		for _, word := range significantWords {
			// Claim matches are most valuable
			if strings.Contains(claimLower, word) {
				score += 3.0
				// Bonus for word appearing multiple times
				score += float64(strings.Count(claimLower, word)-1) * 0.5
			}
			// Evidence matches are also valuable
			if strings.Contains(evidenceText, word) {
				score += 2.0
			}
			// Entity matches
			for _, entity := range fact.Entities {
				if strings.Contains(strings.ToLower(entity), word) {
					score += 2.5
					break
				}
			}
			// Other field matches
			if strings.Contains(strings.ToLower(fact.ControlFamily), word) {
				score += 1.5
			}
			if strings.Contains(strings.ToLower(fact.SectionContext), word) {
				score += 1.0
			}
		}

		// Boost high confidence facts
		if fact.Confidence >= 0.95 {
			score *= 1.2
		} else if fact.Confidence >= 0.9 {
			score *= 1.1
		}

		// Boost facts with specific evidence
		if len(fact.EvidenceQuotes) > 0 || fact.EvidenceQuote != "" {
			score *= 1.1
		}

		if score > 0 {
			scored = append(scored, scoredFact{fact: fact, score: score})
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

	// Return top 15 facts (give Claude more to work with)
	var results []models.ExtractedFact
	for i := 0; i < len(scored) && i < 15; i++ {
		results = append(results, scored[i].fact)
	}

	return results
}

// buildSources builds source results from facts
func (p *Processor) buildSources(facts []models.ExtractedFact) []SourceResult {
	var sources []SourceResult

	for _, fact := range facts {
		source := SourceResult{
			FactIndex:  fact.FactIndex,
			Claim:      fact.Claim,
			Quote:      fact.GetPrimaryQuote(),
			Document:   fact.SourceDoc,
			Location:   fact.SourceLocation,
			Confidence: fact.Confidence,
		}

		// Try to get chunk context by searching for the quote in all chunks
		// (ChunkID from filename can be unreliable due to parallel extraction)
		if p.chunkManager != nil {
			quote := fact.GetPrimaryQuote()
			foundChunk := ""
			usedFallback := false
			if quote != "" {
				// Search all chunks for this quote
				chunk := p.chunkManager.FindChunkContainingQuote(fact.SourceDoc, quote)
				if chunk != nil {
					source.ChunkText = chunk.Text
					foundChunk = chunk.ChunkID
				}
			}

			// Fallback to ChunkID if quote search fails
			if source.ChunkText == "" && fact.ChunkID != "" {
				chunk := p.chunkManager.GetChunk(fact.SourceDoc, fact.ChunkID)
				if chunk != nil {
					source.ChunkText = chunk.Text
					foundChunk = fact.ChunkID
					usedFallback = true
				}
			}

			// Debug: compare FactIndex (stored) vs GlobalIndex (computed at load)
			// If they differ, facts were saved to wrong files or loaded in wrong order
			if fact.FactIndex > 0 && fact.FactIndex != fact.GlobalIndex {
				fmt.Printf("[DEBUG] INDEX MISMATCH: FactIndex=%d (stored) vs GlobalIndex=%d (loaded), ChunkID=%s\n",
					fact.FactIndex, fact.GlobalIndex, fact.ChunkID)
			}

			if source.ChunkText == "" {
				fmt.Printf("[DEBUG] Fact#%d (ChunkID=%s, Loc=%s): NO CHUNK FOUND, quote=%q\n",
					fact.FactIndex, fact.ChunkID, fact.SourceLocation, truncateString(quote, 40))
			} else if foundChunk != fact.ChunkID && !usedFallback {
				// Only log mismatch if quote was found in a different chunk (not via fallback)
				fmt.Printf("[DEBUG] Fact#%d: ChunkID mismatch - stored as %s but quote found in %s\n",
					fact.FactIndex, fact.ChunkID, foundChunk)
			}
		}

		sources = append(sources, source)
	}

	return sources
}

// AnswerStreamCallback is called with each chunk of the answer as it's generated
type AnswerStreamCallback func(chunk string)

// GenerateAnswerStream generates an answer using Claude with streaming output.
// Returns the full answer text when complete.
func (p *Processor) GenerateAnswerStream(ctx context.Context, query string, facts []models.ExtractedFact, onChunk AnswerStreamCallback) (string, error) {
	if p.client == nil {
		return "", fmt.Errorf("no Claude client available")
	}

	prompt := p.buildAnswerPrompt(query, facts)

	return p.client.PromptStream(ctx, prompt, &claude.PromptOptions{
		MaxTokens: 2000,
	}, func(chunk string) {
		if onChunk != nil {
			onChunk(chunk)
		}
	})
}

// buildAnswerPrompt builds the prompt for answer generation
func (p *Processor) buildAnswerPrompt(query string, facts []models.ExtractedFact) string {
	var sb strings.Builder
	sb.WriteString("Based on the following extracted facts from official documents, answer this question.\n\n")

	// Include conversation history so follow-up questions make sense
	if len(p.conversationHistory) > 0 {
		sb.WriteString("Conversation so far:\n")
		for _, turn := range p.conversationHistory {
			sb.WriteString(fmt.Sprintf("User: %s\n", turn.Query))
			sb.WriteString(fmt.Sprintf("Assistant: %s\n\n", turn.Answer))
		}
		sb.WriteString("Now answer the follow-up question using the facts below.\n\n")
	}

	sb.WriteString(fmt.Sprintf("Question: %s\n\n", query))
	sb.WriteString("Available Facts:\n")

	for _, fact := range facts {
		sb.WriteString(fmt.Sprintf("[%d] %s\n", fact.FactIndex, fact.Claim))
		if fact.GetPrimaryQuote() != "" {
			sb.WriteString(fmt.Sprintf("    Evidence: \"%s\"\n", fact.GetPrimaryQuote()))
		}
		sb.WriteString(fmt.Sprintf("    Source: %s, %s\n\n", fact.SourceDoc, fact.SourceLocation))
	}

	sb.WriteString("\nInstructions:\n")
	sb.WriteString("1. Answer the question using ONLY the facts provided above.\n")
	sb.WriteString("2. IMPORTANT: Cite your sources using the fact numbers shown (e.g., [42], [156]).\n")
	sb.WriteString("3. Only cite facts that directly support your statements.\n")
	sb.WriteString("4. If the facts don't fully answer the question, say what's missing.\n")
	sb.WriteString("\nExample format: \"The system uses encryption [42] and requires authentication [156].\"\n")

	return sb.String()
}

// generateAnswer generates an answer using Claude
func (p *Processor) generateAnswer(ctx context.Context, query string, facts []models.ExtractedFact) (string, error) {
	if p.client == nil {
		return "", fmt.Errorf("no Claude client available")
	}

	response, err := p.client.Prompt(ctx, p.buildAnswerPrompt(query, facts), &claude.PromptOptions{
		MaxTokens: 2000,
	})
	if err != nil {
		return "", err
	}

	return response, nil
}

// simpleFallbackAnswer generates a simple answer without Claude
func (p *Processor) simpleFallbackAnswer(query string, facts []models.ExtractedFact) string {
	if len(facts) == 0 {
		return "No relevant information found in the documents."
	}

	var sb strings.Builder
	sb.WriteString("Based on the available documents:\n\n")

	for _, fact := range facts {
		sb.WriteString("- " + fact.Claim + "\n")
	}

	return sb.String()
}

// MultiPassQuery performs multi-pass query for more comprehensive results
func (p *Processor) MultiPassQuery(ctx context.Context, query string, maxPasses int) (*QueryResult, error) {
	if maxPasses <= 1 {
		return p.ProcessQuery(ctx, query)
	}

	// First pass: initial query
	result, err := p.ProcessQuery(ctx, query)
	if err != nil {
		return nil, err
	}

	// Additional passes: refine based on initial results
	for pass := 1; pass < maxPasses; pass++ {
		// Generate follow-up query based on current results
		followUp := p.generateFollowUpQuery(query, result)
		if followUp == "" {
			break
		}

		// Process follow-up
		additionalResult, err := p.ProcessQuery(ctx, followUp)
		if err != nil {
			break
		}

		// Merge results
		result = p.mergeResults(result, additionalResult)
	}

	return result, nil
}

// generateFollowUpQuery generates a follow-up query based on initial results
func (p *Processor) generateFollowUpQuery(originalQuery string, result *QueryResult) string {
	// Look for gaps in the answer
	if strings.Contains(strings.ToLower(result.Answer), "not found") ||
		strings.Contains(strings.ToLower(result.Answer), "no information") {
		return ""
	}

	// For now, just return empty - could be enhanced with LLM-based follow-up generation
	return ""
}

// truncateString truncates a string to maxLen characters
func truncateString(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}

// mergeResults merges two query results
func (p *Processor) mergeResults(r1, r2 *QueryResult) *QueryResult {
	// Combine answers
	combined := r1.Answer
	if r2.Answer != "" && r2.Answer != r1.Answer {
		combined += "\n\nAdditional findings:\n" + r2.Answer
	}

	// Merge sources, deduplicating
	seenClaims := make(map[string]bool)
	var sources []SourceResult
	for _, s := range r1.Sources {
		if !seenClaims[s.Claim] {
			seenClaims[s.Claim] = true
			sources = append(sources, s)
		}
	}
	for _, s := range r2.Sources {
		if !seenClaims[s.Claim] {
			seenClaims[s.Claim] = true
			sources = append(sources, s)
		}
	}

	return &QueryResult{
		Query:   r1.Query,
		Answer:  combined,
		Sources: sources,
	}
}
