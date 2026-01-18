package validation

import (
	"fmt"
	"regexp"
	"strings"
	"unicode"

	"github.com/nesposito/frfr/internal/domain/models"
)

// Validator validates extracted facts against source text
type Validator struct {
	sourceLines []string
	sourceText  string
}

// NewValidator creates a new validator with source text
func NewValidator(sourceText string) *Validator {
	return &Validator{
		sourceLines: strings.Split(sourceText, "\n"),
		sourceText:  sourceText,
	}
}

// ValidationThresholds define match quality levels
const (
	ThresholdValid     = 0.90 // >=90% is valid
	ThresholdNearMatch = 0.75 // 75-89% is near match
	ThresholdMedium    = 0.40 // 40-74% is medium confidence
)

// ValidateFact validates a single fact against the source text
func (v *Validator) ValidateFact(fact *models.ExtractedFact, chunkText string) *models.ValidationResult {
	quote := fact.GetPrimaryQuote()
	if quote == "" {
		return &models.ValidationResult{
			IsValid:      false,
			ErrorMessage: "No evidence quote provided",
			MatchRatio:   0,
		}
	}

	// Parse source location
	startLine, endLine := parseLineNumbers(fact.SourceLocation)

	// Get source text from specified lines
	var sourceText string
	if startLine > 0 && endLine > 0 && startLine <= len(v.sourceLines) {
		endIdx := min(endLine, len(v.sourceLines))
		sourceText = strings.Join(v.sourceLines[startLine-1:endIdx], "\n")
	} else if chunkText != "" {
		sourceText = chunkText
	} else {
		sourceText = v.sourceText
	}

	// Normalize both texts
	normalizedQuote := normalizeText(quote)
	normalizedSource := normalizeText(sourceText)

	// Try exact match first
	if strings.Contains(normalizedSource, normalizedQuote) {
		return &models.ValidationResult{
			IsValid:    true,
			MatchRatio: 1.0,
		}
	}

	// Try word-by-word sequential matching
	matchRatio := sequentialWordMatch(normalizedQuote, normalizedSource)

	result := &models.ValidationResult{
		MatchRatio: matchRatio,
	}

	if matchRatio >= ThresholdValid {
		result.IsValid = true
	} else if matchRatio >= ThresholdNearMatch {
		result.IsValid = true
		result.NearMatch = true
	} else if matchRatio >= ThresholdMedium {
		// Try fuzzy recovery
		recovered := v.attemptRecovery(quote, sourceText)
		if recovered != "" {
			result.IsValid = true
			result.RecoveredQuote = recovered
			result.NearMatch = true
		} else {
			result.IsValid = false
			result.ErrorMessage = "Quote not found in source (medium confidence match)"
		}
	} else {
		result.IsValid = false
		result.ErrorMessage = "Quote not found in source text"
	}

	return result
}

// ValidateAllFacts validates all facts in a result set
func (v *Validator) ValidateAllFacts(facts []models.ExtractedFact, chunkText string) []models.ValidationResult {
	results := make([]models.ValidationResult, len(facts))
	for i := range facts {
		results[i] = *v.ValidateFact(&facts[i], chunkText)
	}
	return results
}

// attemptRecovery tries to find a similar quote in the source
func (v *Validator) attemptRecovery(quote, sourceText string) string {
	quoteWords := tokenize(quote)
	if len(quoteWords) < 3 {
		return ""
	}

	// Find potential matches using first few words as anchor
	anchor := strings.Join(quoteWords[:min(3, len(quoteWords))], " ")
	anchorNorm := normalizeText(anchor)

	// Search for anchor in source
	sourceNorm := normalizeText(sourceText)
	idx := strings.Index(sourceNorm, anchorNorm)
	if idx == -1 {
		// Try fuzzy anchor search
		idx = fuzzyFind(anchorNorm, sourceNorm)
	}

	if idx == -1 {
		return ""
	}

	// Extract a region around the anchor
	regionStart := max(0, idx-50)
	regionEnd := min(len(sourceText), idx+len(quote)+100)
	region := sourceText[regionStart:regionEnd]

	// Try to find the best matching substring
	bestMatch, bestRatio := findBestMatch(quote, region)
	if bestRatio >= ThresholdNearMatch {
		return bestMatch
	}

	return ""
}

// normalizeText normalizes text for comparison
func normalizeText(text string) string {
	// Convert to lowercase
	text = strings.ToLower(text)

	// Replace smart quotes with standard quotes
	text = strings.ReplaceAll(text, "\u201c", "\"")
	text = strings.ReplaceAll(text, "\u201d", "\"")
	text = strings.ReplaceAll(text, "\u2018", "'")
	text = strings.ReplaceAll(text, "\u2019", "'")

	// Normalize dashes
	text = strings.ReplaceAll(text, "\u2013", "-") // en-dash
	text = strings.ReplaceAll(text, "\u2014", "-") // em-dash

	// Normalize whitespace
	text = strings.Join(strings.Fields(text), " ")

	return text
}

// tokenize splits text into words
func tokenize(text string) []string {
	// Split on whitespace and punctuation
	f := func(c rune) bool {
		return unicode.IsSpace(c) || (unicode.IsPunct(c) && c != '-' && c != '\'')
	}
	return strings.FieldsFunc(text, f)
}

// sequentialWordMatch calculates the ratio of words that appear in sequence
func sequentialWordMatch(quote, source string) float64 {
	quoteWords := tokenize(quote)
	sourceWords := tokenize(source)

	if len(quoteWords) == 0 {
		return 0
	}

	matched := 0
	sourceIdx := 0

	for _, qw := range quoteWords {
		qwLower := strings.ToLower(qw)
		for i := sourceIdx; i < len(sourceWords); i++ {
			if strings.ToLower(sourceWords[i]) == qwLower {
				matched++
				sourceIdx = i + 1
				break
			}
			// Try fuzzy word match for OCR errors
			if fuzzyWordMatch(qwLower, strings.ToLower(sourceWords[i])) {
				matched++
				sourceIdx = i + 1
				break
			}
		}
	}

	return float64(matched) / float64(len(quoteWords))
}

// fuzzyWordMatch checks if two words are similar (handles OCR errors)
func fuzzyWordMatch(w1, w2 string) bool {
	if w1 == w2 {
		return true
	}

	// Common OCR substitutions
	ocrSubs := map[string]string{
		"l": "1", "1": "l",
		"0": "o", "o": "0",
		"rn": "m", "m": "rn",
		"vv": "w", "w": "vv",
	}

	for old, new := range ocrSubs {
		if strings.ReplaceAll(w1, old, new) == w2 {
			return true
		}
		if strings.ReplaceAll(w2, old, new) == w1 {
			return true
		}
	}

	// Levenshtein distance for short words
	if len(w1) < 6 && len(w2) < 6 {
		return levenshtein(w1, w2) <= 1
	}

	return false
}

// levenshtein calculates the Levenshtein distance between two strings
func levenshtein(s1, s2 string) int {
	if len(s1) == 0 {
		return len(s2)
	}
	if len(s2) == 0 {
		return len(s1)
	}

	r1 := []rune(s1)
	r2 := []rune(s2)

	// Create matrix
	d := make([][]int, len(r1)+1)
	for i := range d {
		d[i] = make([]int, len(r2)+1)
		d[i][0] = i
	}
	for j := range d[0] {
		d[0][j] = j
	}

	// Fill matrix
	for i := 1; i <= len(r1); i++ {
		for j := 1; j <= len(r2); j++ {
			cost := 1
			if r1[i-1] == r2[j-1] {
				cost = 0
			}
			d[i][j] = min3(
				d[i-1][j]+1,      // deletion
				d[i][j-1]+1,      // insertion
				d[i-1][j-1]+cost, // substitution
			)
		}
	}

	return d[len(r1)][len(r2)]
}

// fuzzyFind finds a fuzzy match location in text
func fuzzyFind(needle, haystack string) int {
	needleWords := strings.Fields(needle)
	if len(needleWords) == 0 {
		return -1
	}

	// Search for first word
	firstWord := needleWords[0]
	haystackWords := strings.Fields(haystack)

	for _, hw := range haystackWords {
		if fuzzyWordMatch(firstWord, hw) {
			// Found potential start, calculate position
			pos := strings.Index(haystack, hw)
			return pos
		}
	}

	return -1
}

// findBestMatch finds the best matching substring
func findBestMatch(quote, source string) (string, float64) {
	quoteLen := len(quote)
	sourceLen := len(source)

	if quoteLen > sourceLen {
		return "", 0
	}

	bestMatch := ""
	bestRatio := 0.0

	// Slide window across source
	for start := 0; start <= sourceLen-quoteLen/2; start++ {
		for length := quoteLen / 2; length <= min(quoteLen*2, sourceLen-start); length++ {
			substr := source[start : start+length]
			ratio := sequentialWordMatch(normalizeText(quote), normalizeText(substr))
			if ratio > bestRatio {
				bestRatio = ratio
				bestMatch = substr
			}
		}
	}

	return bestMatch, bestRatio
}

// parseLineNumbers extracts line numbers from a source location string
func parseLineNumbers(location string) (int, int) {
	re := regexp.MustCompile(`Lines?\s*(\d+)(?:\s*-\s*(\d+))?`)
	matches := re.FindStringSubmatch(location)
	if len(matches) < 2 {
		return 0, 0
	}

	start := 0
	end := 0

	if _, err := regexp.MatchString(`\d+`, matches[1]); err == nil {
		fmt.Sscanf(matches[1], "%d", &start)
	}

	if len(matches) > 2 && matches[2] != "" {
		fmt.Sscanf(matches[2], "%d", &end)
	} else {
		end = start
	}

	return start, end
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func min3(a, b, c int) int {
	result := a
	if b < result {
		result = b
	}
	if c < result {
		result = c
	}
	return result
}
