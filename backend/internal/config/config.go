package config

import (
	"os"
	"path/filepath"
	"strconv"
)

// Config holds all configuration for the frfr backend
type Config struct {
	// Server settings
	Port string

	// Storage paths
	SessionStorageDir string
	InputsDir         string

	// Extraction settings
	SwarmSize          int
	SwarmModel         string
	JudgeModel         string
	ConsensusThreshold float64

	// Chunking settings
	MinChunkChars int
	MaxChunkChars int
	ChunkOverlap  int

	// Claude API settings
	AnthropicAPIKey string
	MaxWorkers      int
	MaxRetries      int
}

// DefaultConfig returns the default configuration
func DefaultConfig() *Config {
	homeDir, _ := os.UserHomeDir()

	return &Config{
		// Server
		Port: getEnv("FRFR_PORT", "8080"),

		// Storage
		SessionStorageDir: getEnv("FRFR_DATA_DIR", filepath.Join(homeDir, "Documents", "frfr", "sessions")),
		InputsDir:         getEnv("FRFR_INPUTS_DIR", filepath.Join(homeDir, "Documents", "frfr", "inputs")),

		// Extraction
		SwarmSize:          getEnvInt("FRFR_SWARM_SIZE", 5),
		SwarmModel:         getEnv("FRFR_SWARM_MODEL", "claude-sonnet-4"),
		JudgeModel:         getEnv("FRFR_JUDGE_MODEL", "claude-opus-4"),
		ConsensusThreshold: getEnvFloat("FRFR_CONSENSUS_THRESHOLD", 0.8),

		// Chunking
		MinChunkChars: getEnvInt("FRFR_MIN_CHUNK_CHARS", 3000),
		MaxChunkChars: getEnvInt("FRFR_MAX_CHUNK_CHARS", 8000),
		ChunkOverlap:  getEnvInt("FRFR_CHUNK_OVERLAP", 200),

		// Claude API (checks env var, macOS keychain, config files)
		AnthropicAPIKey: getAnthropicAPIKey(),
		MaxWorkers:      getEnvInt("FRFR_MAX_WORKERS", 20),
		MaxRetries:      getEnvInt("FRFR_MAX_RETRIES", 3),
	}
}

// Load loads configuration, creating directories if needed
func Load() (*Config, error) {
	cfg := DefaultConfig()

	// Ensure storage directories exist
	if err := os.MkdirAll(cfg.SessionStorageDir, 0755); err != nil {
		return nil, err
	}
	if err := os.MkdirAll(cfg.InputsDir, 0755); err != nil {
		return nil, err
	}

	return cfg, nil
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if i, err := strconv.Atoi(value); err == nil {
			return i
		}
	}
	return defaultValue
}

func getEnvFloat(key string, defaultValue float64) float64 {
	if value := os.Getenv(key); value != "" {
		if f, err := strconv.ParseFloat(value, 64); err == nil {
			return f
		}
	}
	return defaultValue
}

// getAnthropicAPIKey returns explicit API key if set, empty string otherwise.
// When empty, the Claude client will attempt to use native credentials.
func getAnthropicAPIKey() string {
	return os.Getenv("ANTHROPIC_API_KEY")
}
