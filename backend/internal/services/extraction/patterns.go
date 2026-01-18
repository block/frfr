package extraction

import (
	"regexp"
	"strings"
)

// QuantitativeValue represents an extracted quantitative value
type QuantitativeValue struct {
	Value      string `json:"value"`
	Type       string `json:"type"` // frequency, duration, sample_size, percentage, count
	Normalized string `json:"normalized,omitempty"`
}

// ExtractionPatterns provides regex patterns for extracting structured information
type ExtractionPatterns struct{}

// Compiled regex patterns
var (
	// Frequency patterns
	frequencyPatterns = []*regexp.Regexp{
		regexp.MustCompile(`(?i)\b(daily|weekly|monthly|quarterly|semi-annually|annually|yearly)\b`),
		regexp.MustCompile(`(?i)\bevery\s+\d+\s+(day|days|week|weeks|month|months|quarter|quarters|year|years)\b`),
		regexp.MustCompile(`(?i)\b\d+\s+times?\s+per\s+(day|week|month|quarter|year)\b`),
		regexp.MustCompile(`(?i)\b(real-time|continuous|continuously|ongoing)\b`),
		regexp.MustCompile(`(?i)\bupon\s+(occurrence|detection|notification|request)\b`),
		regexp.MustCompile(`(?i)\bwithin\s+\d+\s+(hour|hours|day|days|business\s+days?)\b`),
		regexp.MustCompile(`(?i)\b(at\s+least|no\s+less\s+than|minimum\s+of)\s+\d+\s+times?\s+(per|each)\s+(day|week|month|quarter|year)\b`),
		regexp.MustCompile(`(?i)\bon\s+a\s+(daily|weekly|monthly|quarterly|yearly|regular)\s+basis\b`),
	}

	// Duration patterns
	durationPatterns = []*regexp.Regexp{
		regexp.MustCompile(`(?i)\b\d+\s+(day|days|week|weeks|month|months|quarter|quarters|year|years)\b`),
		regexp.MustCompile(`(?i)\b\d+\s+(hour|hours|minute|minutes|second|seconds)\b`),
		regexp.MustCompile(`(?i)\b\d+-(?:day|week|month|year)\s+(?:period|retention|window)\b`),
	}

	// Sample size patterns
	sampleSizePatterns = []*regexp.Regexp{
		regexp.MustCompile(`(?i)\bsampled?\s+\d+\s+(?:of\s+\d+)?\s*(?:items?|users?|employees?|tickets?|controls?|instances?|requests?|reviews?|reports?)?\b`),
		regexp.MustCompile(`(?i)\bsample\s+of\s+\d+\b`),
		regexp.MustCompile(`(?i)\binspected\s+(?:all\s+)?\d+\s+(?:items?|users?|employees?|tickets?|controls?|instances?|requests?|reviews?|reports?)\b`),
		regexp.MustCompile(`(?i)\btested\s+\d+\s+(?:items?|users?|employees?|tickets?|controls?|instances?)\b`),
		regexp.MustCompile(`(?i)\b(?:reviewed|examined|analyzed)\s+\d+\s+(?:out\s+of\s+)?\d*\s*(?:items?|samples?)\b`),
	}

	// Percentage patterns
	percentagePatterns = []*regexp.Regexp{
		regexp.MustCompile(`(?i)\b\d+(?:\.\d+)?%\b`),
		regexp.MustCompile(`(?i)\b\d+\s+percent\b`),
		regexp.MustCompile(`(?i)\b(?:greater|less|more|fewer)\s+than\s+\d+%?\b`),
		regexp.MustCompile(`(?i)\b(?:at|above|below|exceeds|falls\s+below)\s+\d+%?\b`),
		regexp.MustCompile(`(?i)\buptime\s+of\s+\d+(?:\.\d+)?%\b`),
	}

	// Count patterns
	countPatterns = []*regexp.Regexp{
		regexp.MustCompile(`(?i)\b\d+\s+(?:employees?|users?|offices?|countries|locations?|servers?|systems?|controls?|policies|procedures?)\b`),
		regexp.MustCompile(`(?i)\b\d+\+?\s+(?:employees?|users?|offices?)\b`),
		regexp.MustCompile(`(?i)\b(?:over|more\s+than|approximately)\s+\d+(?:,\d+)?\s+(?:employees?|users?|offices?|countries)\b`),
	}

	// Technical spec patterns
	encryptionPatterns = []*regexp.Regexp{
		regexp.MustCompile(`(?i)\b(?:TLS|SSL)\s+(?:v?(?:1\.0|1\.1|1\.2|1\.3))?\b`),
		regexp.MustCompile(`(?i)\b(?:AES|RSA|SHA|MD5)-?\d+\b`),
		regexp.MustCompile(`(?i)\b\d+-bit\s+(?:encryption|key|algorithm)\b`),
		regexp.MustCompile(`(?i)\b(?:AES|RSA|SHA|DES|3DES|Blowfish|bcrypt)\b`),
	}

	authenticationPatterns = []*regexp.Regexp{
		regexp.MustCompile(`(?i)\b(?:two|2|multi)[-\s]?factor\s+authentication\b`),
		regexp.MustCompile(`(?i)\b(?:MFA|2FA|SSO|SAML|OAuth|LDAP|AD|Kerberos)\b`),
		regexp.MustCompile(`(?i)\bpassword\s+(?:complexity|length|history|age)\b`),
		regexp.MustCompile(`(?i)\b(?:minimum|maximum)\s+password\s+(?:length|age)\s+of\s+\d+\b`),
	}

	networkPatterns = []*regexp.Regexp{
		regexp.MustCompile(`(?i)\b(?:firewall|IDS|IPS|DMZ|VPN|VLAN)\b`),
		regexp.MustCompile(`(?i)\b(?:port|ports)\s+\d+(?:\s+and\s+\d+)?\b`),
		regexp.MustCompile(`(?i)\b(?:stateful|stateless)\s+(?:packet\s+)?inspection\b`),
		regexp.MustCompile(`(?i)\b(?:inbound|outbound)\s+(?:traffic|connections?|rules?)\b`),
	}

	rolePatterns = []*regexp.Regexp{
		regexp.MustCompile(`(?i)\b(?:Chief|Senior|VP\s+of|Vice\s+President\s+of|Director\s+of|Manager\s+of|Head\s+of)\s+[A-Z][a-zA-Z\s]+\b`),
		regexp.MustCompile(`(?i)\b(?:Security|IT|Privacy|Compliance|Risk|Audit|Operations?|Engineering)\s+(?:Team|Officer|Administrator|Manager|Personnel|Staff|Department)\b`),
		regexp.MustCompile(`(?i)\b(?:CISO|CIO|CTO|CPO|DPO|CSO)\b`),
		regexp.MustCompile(`(?i)\b(?:authorized|designated|responsible)\s+personnel\b`),
	}
)

// ExtractFrequencies extracts all frequency mentions from text
func (p *ExtractionPatterns) ExtractFrequencies(text string) []QuantitativeValue {
	var results []QuantitativeValue
	seen := make(map[string]bool)

	for _, pattern := range frequencyPatterns {
		matches := pattern.FindAllString(text, -1)
		for _, match := range matches {
			if !seen[match] {
				seen[match] = true
				results = append(results, QuantitativeValue{
					Value:      match,
					Type:       "frequency",
					Normalized: normalizeFrequency(match),
				})
			}
		}
	}
	return results
}

// ExtractDurations extracts all duration mentions from text
func (p *ExtractionPatterns) ExtractDurations(text string) []QuantitativeValue {
	var results []QuantitativeValue
	seen := make(map[string]bool)

	for _, pattern := range durationPatterns {
		matches := pattern.FindAllString(text, -1)
		for _, match := range matches {
			if !seen[match] {
				seen[match] = true
				results = append(results, QuantitativeValue{
					Value: match,
					Type:  "duration",
				})
			}
		}
	}
	return results
}

// ExtractSampleSizes extracts all sample size mentions from text
func (p *ExtractionPatterns) ExtractSampleSizes(text string) []QuantitativeValue {
	var results []QuantitativeValue
	seen := make(map[string]bool)

	for _, pattern := range sampleSizePatterns {
		matches := pattern.FindAllString(text, -1)
		for _, match := range matches {
			if !seen[match] {
				seen[match] = true
				results = append(results, QuantitativeValue{
					Value: match,
					Type:  "sample_size",
				})
			}
		}
	}
	return results
}

// ExtractPercentages extracts all percentage/threshold mentions from text
func (p *ExtractionPatterns) ExtractPercentages(text string) []QuantitativeValue {
	var results []QuantitativeValue
	seen := make(map[string]bool)

	for _, pattern := range percentagePatterns {
		matches := pattern.FindAllString(text, -1)
		for _, match := range matches {
			if !seen[match] {
				seen[match] = true
				results = append(results, QuantitativeValue{
					Value: match,
					Type:  "percentage",
				})
			}
		}
	}
	return results
}

// ExtractCounts extracts all count mentions from text
func (p *ExtractionPatterns) ExtractCounts(text string) []QuantitativeValue {
	var results []QuantitativeValue
	seen := make(map[string]bool)

	for _, pattern := range countPatterns {
		matches := pattern.FindAllString(text, -1)
		for _, match := range matches {
			if !seen[match] {
				seen[match] = true
				results = append(results, QuantitativeValue{
					Value: match,
					Type:  "count",
				})
			}
		}
	}
	return results
}

// ExtractAllQuantitative extracts all quantitative values from text
func (p *ExtractionPatterns) ExtractAllQuantitative(text string) []QuantitativeValue {
	var results []QuantitativeValue
	results = append(results, p.ExtractFrequencies(text)...)
	results = append(results, p.ExtractDurations(text)...)
	results = append(results, p.ExtractSampleSizes(text)...)
	results = append(results, p.ExtractPercentages(text)...)
	results = append(results, p.ExtractCounts(text)...)
	return results
}

// ExtractEncryptionSpecs extracts encryption specifications from text
func (p *ExtractionPatterns) ExtractEncryptionSpecs(text string) []string {
	return extractUniqueMatches(encryptionPatterns, text)
}

// ExtractAuthenticationSpecs extracts authentication specifications from text
func (p *ExtractionPatterns) ExtractAuthenticationSpecs(text string) []string {
	return extractUniqueMatches(authenticationPatterns, text)
}

// ExtractNetworkSpecs extracts network specifications from text
func (p *ExtractionPatterns) ExtractNetworkSpecs(text string) []string {
	return extractUniqueMatches(networkPatterns, text)
}

// ExtractRoles extracts role/WHO mentions from text
func (p *ExtractionPatterns) ExtractRoles(text string) []string {
	return extractUniqueMatches(rolePatterns, text)
}

func extractUniqueMatches(patterns []*regexp.Regexp, text string) []string {
	seen := make(map[string]bool)
	var results []string

	for _, pattern := range patterns {
		matches := pattern.FindAllString(text, -1)
		for _, match := range matches {
			lower := strings.ToLower(match)
			if !seen[lower] {
				seen[lower] = true
				results = append(results, match)
			}
		}
	}
	return results
}

func normalizeFrequency(freqText string) string {
	lower := strings.ToLower(freqText)
	switch {
	case strings.Contains(lower, "daily") || strings.Contains(lower, "every day"):
		return "daily"
	case strings.Contains(lower, "weekly") || strings.Contains(lower, "every week"):
		return "weekly"
	case strings.Contains(lower, "monthly") || strings.Contains(lower, "every month"):
		return "monthly"
	case strings.Contains(lower, "quarterly") || strings.Contains(lower, "every quarter"):
		return "quarterly"
	case strings.Contains(lower, "annually") || strings.Contains(lower, "yearly") || strings.Contains(lower, "every year"):
		return "annually"
	case strings.Contains(lower, "real-time") || strings.Contains(lower, "continuous"):
		return "continuous"
	default:
		return freqText
	}
}

// CalculateSpecificityScore calculates specificity score based on presence of concrete details
func CalculateSpecificityScore(claim string, quantValues, entities []string, processDetails map[string]string) float64 {
	score := 0.3 // Base score

	// Check for quantitative values
	if len(quantValues) > 0 {
		score += 0.2
	}

	// Check for named entities
	if len(entities) > 0 {
		score += 0.2
	}

	// Check for specific roles
	who := processDetails["who"]
	whoLower := strings.ToLower(who)
	if who != "" && whoLower != "management" && whoLower != "personnel" && whoLower != "staff" && whoLower != "it personnel" {
		score += 0.2
	}

	// Check for process details
	if processDetails["who"] != "" {
		score += 0.1
	}
	if processDetails["when"] != "" {
		score += 0.1
	}
	if processDetails["how"] != "" {
		score += 0.1
	}

	// Penalize vague terms
	claimLower := strings.ToLower(claim)
	vagueTerms := []string{"periodically", "regularly", "as needed", "as appropriate", "certain", "various"}
	for _, term := range vagueTerms {
		if strings.Contains(claimLower, term) {
			score -= 0.2
			break
		}
	}

	// Clamp to [0.0, 1.0]
	if score < 0 {
		return 0
	}
	if score > 1 {
		return 1
	}
	return score
}
