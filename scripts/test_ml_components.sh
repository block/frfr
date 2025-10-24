#!/bin/bash
# Test ML/embeddings components (sentence-transformers, numpy, scikit-learn)

set -e

SUCCESS=0
FAILURE=1

echo "Testing ML Components..."
echo "=============================="

# Test 1: numpy
echo -n "  Checking numpy... "
if python -c "import numpy" 2>/dev/null; then
    VERSION=$(python -c "import numpy; print(numpy.__version__)" 2>/dev/null)
    echo "✓ v$VERSION"
else
    echo "✗ Not installed"
    exit $FAILURE
fi

# Test 2: numpy functionality
echo -n "  Testing numpy operations... "
if python -c "
import numpy as np
arr = np.array([1, 2, 3, 4, 5])
assert arr.mean() == 3.0
assert arr.std() > 0
" 2>/dev/null; then
    echo "✓ Operations working"
else
    echo "✗ Numpy operations failed"
    exit $FAILURE
fi

# Test 3: scikit-learn
echo -n "  Checking scikit-learn... "
if python -c "import sklearn" 2>/dev/null; then
    VERSION=$(python -c "import sklearn; print(sklearn.__version__)" 2>/dev/null)
    echo "✓ v$VERSION"
else
    echo "✗ Not installed"
    exit $FAILURE
fi

# Test 4: scikit-learn clustering
echo -n "  Testing clustering algorithms... "
if python -c "
import numpy as np
from sklearn.cluster import KMeans

# Simple clustering test
X = np.array([[1, 2], [1, 4], [1, 0], [10, 2], [10, 4], [10, 0]])
kmeans = KMeans(n_clusters=2, random_state=0, n_init='auto').fit(X)
labels = kmeans.labels_
assert len(labels) == 6
assert len(set(labels)) == 2
" 2>/dev/null; then
    echo "✓ Clustering working"
else
    echo "✗ Clustering failed"
    exit $FAILURE
fi

# Test 5: scikit-learn cosine similarity
echo -n "  Testing cosine similarity... "
if python -c "
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Test cosine similarity
vec1 = np.array([[1, 0, 1, 0]])
vec2 = np.array([[1, 1, 1, 1]])
similarity = cosine_similarity(vec1, vec2)[0][0]
assert 0 <= similarity <= 1
" 2>/dev/null; then
    echo "✓ Similarity calculation working"
else
    echo "✗ Similarity calculation failed"
    exit $FAILURE
fi

# Test 6: sentence-transformers
echo -n "  Checking sentence-transformers... "
if python -c "import sentence_transformers" 2>/dev/null; then
    VERSION=$(python -c "import sentence_transformers; print(sentence_transformers.__version__)" 2>/dev/null)
    echo "✓ v$VERSION"
else
    echo "✗ Not installed"
    exit $FAILURE
fi

# Test 7: sentence-transformers model loading (lightweight model)
echo -n "  Testing sentence-transformers model loading... "
# This will download the model on first run, which may take time
if timeout 120 python << 'EOF' 2>/dev/null
from sentence_transformers import SentenceTransformer
import os

# Use a small model for testing
model_name = 'all-MiniLM-L6-v2'
print(f"Loading model {model_name}... ", end="", flush=True)

try:
    model = SentenceTransformer(model_name)
    print("loaded. ", end="", flush=True)

    # Test embedding generation
    sentences = ["This is a test sentence.", "This is another test."]
    embeddings = model.encode(sentences)

    assert embeddings.shape[0] == 2
    assert embeddings.shape[1] == 384  # MiniLM-L6 produces 384-dim embeddings
    assert embeddings.dtype.name.startswith('float')

    print("✓ Model working", end="")
except Exception as e:
    print(f"✗ Error: {e}", end="")
    exit(1)
EOF
then
    echo ""
else
    echo "✗ Model loading failed or timed out"
    echo "    (This is normal on first run - model needs to download)"
    echo "    (Run the test again after model downloads)"
    exit $FAILURE
fi

# Test 8: Test embedding similarity
echo -n "  Testing embedding similarity... "
if python << 'EOF' 2>/dev/null
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

model = SentenceTransformer('all-MiniLM-L6-v2')

# Similar sentences should have high similarity
sent1 = "The cat sits on the mat."
sent2 = "A cat is sitting on a mat."
sent3 = "The dog runs in the park."

embeddings = model.encode([sent1, sent2, sent3])

sim_12 = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
sim_13 = cosine_similarity([embeddings[0]], [embeddings[2]])[0][0]

# Similar sentences should have higher similarity
assert sim_12 > sim_13
assert sim_12 > 0.7  # Should be quite similar

print("✓ Semantic similarity working", end="")
EOF
then
    echo ""
else
    echo "✗ Embedding similarity test failed"
    exit $FAILURE
fi

echo ""
echo "ML component tests passed!"
exit $SUCCESS
