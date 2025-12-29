#!/bin/bash
# SWE-bench Environment Setup Script
# Sets up environment for Component 3 testing

set -e

echo "================================================================================"
echo "SWE-BENCH ENVIRONMENT SETUP"
echo "================================================================================"
echo ""

# Check conda environment
if ! conda env list | grep -q "testing.*\*"; then
    echo "ERROR: Not in 'testing' conda environment"
    echo "Please run: conda activate testing"
    exit 1
fi

echo "✓ Conda environment: testing (active)"

# Check Docker
if ! docker ps > /dev/null 2>&1; then
    echo "ERROR: Docker is not running or not accessible"
    echo "Please start Docker daemon"
    exit 1
fi

echo "✓ Docker: available (version $(docker --version | awk '{print $3}'))"

# Check Python packages
echo ""
echo "Checking Python packages..."

PACKAGES=(
    "datasets"
    "openai"
    "rich"
    "pyyaml"
)

for pkg in "${PACKAGES[@]}"; do
    if python -c "import $pkg" 2>/dev/null; then
        VERSION=$(python -c "import $pkg; print($pkg.__version__)" 2>/dev/null || echo "unknown")
        echo "✓ $pkg: $VERSION"
    else
        echo "✗ $pkg: NOT INSTALLED"
        echo "  Installing..."
        pip install -q $pkg
        echo "✓ $pkg: installed"
    fi
done

# Check SWE-bench specific modules
echo ""
echo "Checking SWE-bench modules..."

if python -c "from bench_agent.runner.swebench_runner import run_swebench_eval" 2>/dev/null; then
    echo "✓ SWE-bench runner: available"
else
    echo "✗ SWE-bench runner: NOT AVAILABLE"
    exit 1
fi

# Check OpenAI API key
echo ""
echo "Checking OpenAI API key..."

if [ -z "$OPENAI_API_KEY" ]; then
    echo "WARNING: OPENAI_API_KEY not set"
    echo "Please set it: export OPENAI_API_KEY='your-key'"
    echo ""
    echo "Component 3 requires GPT-4o for JSON generation"
    echo ""
else
    KEY_PREFIX="${OPENAI_API_KEY:0:8}"
    echo "✓ OPENAI_API_KEY: ${KEY_PREFIX}..."
fi

# Check PYTHONPATH
echo ""
echo "Checking PYTHONPATH..."

REQUIRED_PATH="/home/jin/prj_ws/agenticAI/Test-Aware_Debugging_Loop"
if [[ ":$PYTHONPATH:" == *":$REQUIRED_PATH:"* ]]; then
    echo "✓ PYTHONPATH includes: $REQUIRED_PATH"
else
    echo "WARNING: PYTHONPATH does not include project root"
    echo "Setting PYTHONPATH..."
    export PYTHONPATH="$REQUIRED_PATH:$PYTHONPATH"
    echo "✓ PYTHONPATH: $PYTHONPATH"
fi

# Check Component 3 modules
echo ""
echo "Checking Component 3 modules..."

MODULES=(
    "bench_agent.editor.anchor_extractor"
    "bench_agent.editor.edit_applier"
    "bench_agent.editor.edit_validator"
    "bench_agent.editor.diff_generator"
    "bench_agent.protocol.edit_script_workflow"
)

for module in "${MODULES[@]}"; do
    if python -c "import $module" 2>/dev/null; then
        echo "✓ $module"
    else
        echo "✗ $module: IMPORT FAILED"
        exit 1
    fi
done

# Create necessary directories
echo ""
echo "Creating directories..."

DIRS=(
    "outputs"
    "logs"
    "/tmp/swe-bench-repos"
)

for dir in "${DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo "✓ Created: $dir"
    else
        echo "✓ Exists: $dir"
    fi
done

# Summary
echo ""
echo "================================================================================"
echo "ENVIRONMENT SETUP COMPLETE"
echo "================================================================================"
echo ""
echo "Summary:"
echo "  ✓ Conda environment: testing"
echo "  ✓ Docker: available"
echo "  ✓ Python packages: installed"
echo "  ✓ SWE-bench runner: available"
echo "  ✓ Component 3 modules: available"
echo "  ✓ Directories: created"
echo ""

if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠ WARNING: OPENAI_API_KEY not set"
    echo "   Set it before running tests: export OPENAI_API_KEY='your-key'"
    echo ""
fi

echo "Ready to run Component 3 tests!"
echo ""
echo "Quick Test (single instance):"
echo "  USE_EDIT_SCRIPT=1 python scripts/run_mvp.py \\"
echo "    --config configs/p091_component3_single_test.yaml \\"
echo "    --run-id p091-component3-test-\$(date +%Y%m%d-%H%M%S)"
echo ""
echo "Full Test (4 instances):"
echo "  ./run_component3_full_test.sh"
echo ""
