#!/usr/bin/env bash
# Quick start guide for AssessIQ Recruiter Intent Upgrade

echo "=================================================="
echo "AssessIQ Recruiter Intent Upgrade - Quick Start"
echo "=================================================="
echo ""

# Check if backend is running
echo "[1/4] Checking backend..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "    Backend already running"
else
    echo "    Starting backend..."
    python -m app.main > /tmp/backend.log 2>&1 &
    sleep 5
    echo "    Backend started (PID: $!)"
fi

echo ""
echo "[2/4] Running quick diagnostics..."
python scripts/run_diagnostics.py

echo ""
echo "[3/4] Summary of new capabilities:"
echo "    - Role Normalization: 24 canonical roles"
echo "    - Clarification Memory: No more repetitive questions"
echo "    - Domain Filtering: Python!=Java, Sales!=Coding"
echo "    - Smart Clarifications: Max 2 questions before recommending"
echo "    - Recruiter-Grade Responses: Insights + use cases"

echo ""
echo "[4/4] To run full validation:"
echo "    python scripts/recruiter_domain_tests.py"

echo ""
echo "=================================================="
echo "Implementation complete and ready for production!"
echo "=================================================="
