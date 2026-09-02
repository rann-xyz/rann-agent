# 🚀 Quick Start Guide

Get Rann Agent running in 3 minutes!

## ⚡ Installation

### 1. Clone & Install
```bash
git clone https://github.com/rann-xyz/rann-agent.git
cd rann-agent
chmod +x install.sh
./install.sh
```

The installer will:
- ✅ Create virtual environment
- ✅ Install all dependencies
- ✅ Set up the package

### 2. Activate Virtual Environment
```bash
source venv/bin/activate
```

---

## 🎮 Choose Your Interface

### 💻 Option 1: Terminal Application (CLI)

**Best for:** Power users, SSH access, scripting

```bash
python terminal_app.py
```

**Features:**
- 🎨 Beautiful Rich UI with colors
- ⚡ Fast and lightweight
- 📊 Tables and formatted output
- 🖥️ Works over SSH

**Example Session:**
```
╔═══════════════════════════════════════════╗
║   🤖 RANN AGENT - AI CODING ASSISTANT    ║
╚═══════════════════════════════════════════╝

rann> help
rann> index
rann> find UserService
rann> code Build REST API with FastAPI
rann> status
rann> exit
```

---

### 🌐 Option 2: Web Application (Browser)

**Best for:** Visual interface, multiple sessions, sharing

```bash
python web_app.py
```

Then open: **http://localhost:8000**

**Features:**
- 🎨 Modern dark UI with gradients
- 🔴 Real-time WebSocket updates
- 📊 Live statistics dashboard
- 💬 Chat-style interface
- 🎯 Quick action buttons

---

## 🎯 Common Commands

Both applications support the same commands:

### **🤖 Autonomous Coding** (Devin-like)
```bash
code <description>      # Full development workflow
implement <feature>     # Implement a feature
debug <error>          # Smart debugging
test <function>        # Generate tests
review <file>          # Code review
```

### **📚 Codebase Intelligence** (Cursor-like)
```bash
index                  # Index entire codebase
find <symbol>          # Find functions/classes
search <query>         # Semantic code search
context <file>         # Get file context
summary                # Codebase overview
```

### **💡 Smart Completion** (Copilot-like)
```bash
complete <code>        # Get code suggestions
suggest <file>         # Refactoring hints
explain <code>         # Explain code
```

### **⚙️ General**
```bash
help                   # Show all commands
status                 # Agent status
workspace <path>       # Change workspace
```

---

## 📝 Example Workflow

### 1. Index Your Codebase
```bash
rann> workspace /path/to/your/project
rann> index
```

### 2. Find Something
```bash
rann> find UserService
rann> search authentication logic
```

### 3. Code Autonomously
```bash
rann> code Add user registration endpoint with email validation
```

The agent will:
1. ✅ Plan the implementation
2. ✅ Write the code
3. ✅ Generate tests
4. ✅ Debug any errors
5. ✅ Review code quality

### 4. Get Completions
```bash
rann> complete def calculate_total(items):
```

---

## 🔧 Configuration

### Set Your API Keys

Create `.env` file:
```bash
# Anthropic (Claude)
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI (GPT)
OPENAI_API_KEY=sk-...

# Or custom provider
CUSTOM_API_KEY=your-key
CUSTOM_API_BASE=https://api.example.com
```

### Customize Settings

Edit `config.yaml`:
```yaml
agent:
  llm:
    provider: anthropic  # or openai, custom
    model: claude-3-5-sonnet-20241022
    max_tokens: 8192
    temperature: 0.7
```

---

## 🐛 Troubleshooting

### Import Errors
```bash
# Reinstall dependencies
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### Port Already in Use (Web App)
```bash
# Change port in web_app.py
uvicorn.run(app, host="0.0.0.0", port=8001)  # Change 8000 to 8001
```

### Module Not Found
```bash
# Make sure you're in the virtual environment
source venv/bin/activate

# And in the right directory
cd rann-agent
```

---

## 📚 Learn More

- **Full Documentation:** [LOCALHOST_APPS.md](LOCALHOST_APPS.md)
- **AI Features Comparison:** [AI_CODING_FEATURES.md](AI_CODING_FEATURES.md)
- **Main README:** [README.md](README.md)

---

## 💪 What Makes Rann Agent Special?

✅ **Combines Best of All AI Coding Tools:**
- Devin's autonomy (full end-to-end coding)
- Cursor's intelligence (deep codebase understanding)
- Copilot's assistance (smart completions)
- Claude Code's power (terminal + browser access)

✅ **PLUS Unique Features:**
- 🧠 Long-term memory (never forgets)
- 🤖 Multi-agent orchestration
- ⏰ Cron scheduling
- 👤 User modeling
- 🔍 Cross-session search

✅ **Two Powerful Interfaces:**
- Terminal for power users
- Web for visual experience

---

## 🎉 You're Ready!

Start coding with AI:

```bash
# Terminal
python terminal_app.py

# Or Web
python web_app.py
# Then open http://localhost:8000
```

**Happy coding! 🚀**

---

**Questions?** Check the docs or open an issue on GitHub!

**GitHub:** https://github.com/rann-xyz/rann-agent
