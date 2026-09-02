#!/bin/bash
# Script to push to GitHub

echo "🚀 Pushing Rann Agent to GitHub..."
echo ""

# Check if gh CLI is available
if command -v gh &> /dev/null; then
    echo "✅ GitHub CLI found"
    
    # Create repo if it doesn't exist
    gh repo create rann-xyz/rann-agent --public --source=. --remote=origin --push
    
    echo ""
    echo "✅ Repository created and pushed!"
    echo "🔗 https://github.com/rann-xyz/rann-agent"
else
    echo "⚠️  GitHub CLI not found. Manual setup required:"
    echo ""
    echo "1. Create repo on GitHub: https://github.com/new"
    echo "   Name: rann-agent"
    echo "   Public repository"
    echo ""
    echo "2. Add remote and push:"
    echo "   git remote add origin https://github.com/rann-xyz/rann-agent.git"
    echo "   git branch -M main"
    echo "   git push -u origin main"
fi
