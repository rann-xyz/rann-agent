# 🖥️ Rann Agent - Localhost Applications

Dua cara untuk interact dengan Rann Agent: **Terminal CLI** dan **Web Interface**!

---

## 🚀 **Quick Start**

### **Install Dependencies**

```bash
cd rann-agent
pip install -r requirements-app.txt
```

---

## 💻 **1. TERMINAL APPLICATION**

Interactive CLI dengan Rich UI yang cantik!

### **Run**

```bash
python terminal_app.py
```

### **Features**

✅ **Beautiful Terminal UI**
- Rich formatting dengan colors
- Interactive prompts
- Real-time status
- Tables dan panels

✅ **Available Commands**

**General:**
- `help` - Show all commands
- `status` - Show agent status
- `clear` - Clear screen
- `workspace <path>` - Change workspace
- `exit` - Exit application

**Coding Commands:**
- `code <description>` - Autonomous coding
  - Example: `code Build REST API for users`
- `implement <feature>` - Implement feature
- `debug <error>` - Debug an error
- `test <function>` - Generate tests
- `review <file>` - Review code

**Codebase Commands:**
- `index` - Index entire codebase
- `find <symbol>` - Find function/class
  - Example: `find UserService`
- `search <query>` - Search in code
- `context <file>` - Get file context
- `summary` - Codebase summary

**Completion Commands:**
- `complete <code>` - Get code completions
  - Example: `complete def hello():`
- `suggest <file>` - Suggest improvements
- `explain <code>` - Explain code

### **Screenshots (Terminal)**

```
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   ██████╗  █████╗ ███╗   ██╗███╗   ██╗                  ║
║   ██╔══██╗██╔══██╗████╗  ██║████╗  ██║                  ║
║   ██████╔╝███████║██╔██╗ ██║██╔██╗ ██║                  ║
║   ██╔══██╗██╔══██║██║╚██╗██║██║╚██╗██║                  ║
║   ██║  ██║██║  ██║██║ ╚████║██║ ╚████║                  ║
║   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═══╝                  ║
║                                                           ║
║        🤖 AUTONOMOUS AI CODING AGENT 🚀                   ║
║        By Papa Agis (@rann_xyz)                          ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

🔥 THE MOST ADVANCED AI AGENT
Type 'help' for commands, 'exit' to quit

rann> _
```

### **Example Usage**

```bash
# Index codebase
rann> index
📚 Indexing codebase...
✅ Indexing Complete
┌────────────────┬──────────┐
│ Metric         │ Value    │
├────────────────┼──────────┤
│ Total Files    │ 42       │
│ Total Lines    │ 5,234    │
│   Python       │ 38       │
│   JavaScript   │ 4        │
└────────────────┴──────────┘

# Find a symbol
rann> find UserService
🔍 Searching for 'UserService'...
┌──────────────────────────┬───────┬──────┐
│ File                     │ Type  │ Line │
├──────────────────────────┼───────┼──────┤
│ services/user_service.py │ class │ 15   │
└──────────────────────────┴───────┴──────┘

# Autonomous coding
rann> code Build user authentication API with JWT
🤖 Starting autonomous coding...
Task: Build user authentication API with JWT

✅ Task Completed
┌─────────────────┬────────┐
│ Metric          │ Value  │
├─────────────────┼────────┤
│ Status          │ completed │
│ Files Modified  │ 3      │
│ Tests Written   │ 1      │
│ Bugs Fixed      │ 0      │
└─────────────────┴────────┘
```

---

## 🌐 **2. WEB APPLICATION**

Modern web interface dengan real-time WebSocket!

### **Run**

```bash
python web_app.py
```

Kemudian buka browser: **http://localhost:8000**

### **Features**

✅ **Beautiful Modern UI**
- Dark theme dengan gradient accents
- Responsive design
- Real-time updates via WebSocket
- Smooth animations

✅ **Live Statistics**
- Tasks completed
- Files indexed
- Lines of code
- Success rate

✅ **Interactive Chat**
- Real-time messaging
- Quick action buttons
- Command history
- Auto-scroll

✅ **Same Commands as Terminal**
All terminal commands work in web interface!

### **Screenshots (Web)**

**Homepage:**
```
╔══════════════════════════════════════════════════════════╗
║  🤖 Rann Agent                                  🟢 Online ║
║  The Most Advanced AI Coding Agent                       ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  ┌─────────────┐  ┌────────────────────────────────┐   ║
║  │ STATS       │  │ CHAT                           │   ║
║  │             │  │                                │   ║
║  │ Tasks: 12   │  │ 👋 Hi! Aku Rann Agent...      │   ║
║  │ Files: 42   │  │                                │   ║
║  │ Lines: 5.2k │  │ [Quick Actions]                │   ║
║  │             │  │ 📚 Index  📊 Status  ❓ Help   │   ║
║  └─────────────┘  │                                │   ║
║                   │ > Type a command...      [Send]│   ║
║                   └────────────────────────────────┘   ║
╚══════════════════════════════════════════════════════════╝
```

### **Example Usage**

1. Open **http://localhost:8000**
2. Click **"📚 Index Codebase"** quick action
3. Type commands in chat: `find UserService`
4. See results in real-time!

---

## 🎯 **Which One to Use?**

### **Use Terminal App When:**
- ✅ You love CLI and keyboard shortcuts
- ✅ Working on remote server via SSH
- ✅ Want lightweight without browser
- ✅ Scripting and automation

### **Use Web App When:**
- ✅ You prefer visual UI
- ✅ Want to share screen with team
- ✅ Need multiple tabs/sessions
- ✅ Like modern web interfaces

---

## 🔥 **Features Comparison**

| Feature | Terminal | Web |
|---------|----------|-----|
| **UI** | Rich CLI | Modern Web |
| **Speed** | ⚡ Instant | 🚀 Fast |
| **Real-time** | ✅ | ✅ WebSocket |
| **Stats Dashboard** | Table | Live Cards |
| **Commands** | All ✅ | All ✅ |
| **Multi-session** | ❌ | ✅ |
| **Shareable** | ❌ | ✅ URL |
| **Keyboard Shortcuts** | ✅ | ⚠️ Basic |
| **Resource Usage** | 🪶 Light | 💻 Medium |

---

## 🛠️ **Advanced Usage**

### **Terminal: Change Workspace**

```bash
rann> workspace /path/to/project
✅ Workspace changed to: /path/to/project

rann> index
# Now indexing the new project
```

### **Web: Access from Network**

Edit `web_app.py` line:
```python
uvicorn.run(app, host="0.0.0.0", port=8000)
```

Then access from other devices:
```
http://192.168.1.100:8000
```

### **Both: Use with Custom Port**

**Terminal:** No port needed (local only)

**Web:**
```python
# Change port in web_app.py
uvicorn.run(app, host="0.0.0.0", port=3000)
```

---

## 🚀 **Performance Tips**

### **For Large Codebases:**

1. **Index specific extensions:**
```bash
# In code, modify:
await context.index_codebase(extensions=['.py', '.js'])
```

2. **Limit search results:**
```bash
rann> search authentication
# Returns top 10 by default
```

3. **Use workspace to focus:**
```bash
rann> workspace ./specific-module
rann> index
```

---

## 📊 **Architecture**

```
┌─────────────────────────────────────────────┐
│           USER INTERFACES                   │
├────────────────┬────────────────────────────┤
│  Terminal CLI  │    Web Browser             │
│  (terminal_app)│    (web_app)               │
└────────┬───────┴────────┬───────────────────┘
         │                │
         └────────┬───────┘
                  │
         ┌────────▼────────┐
         │  Rann Agent Core│
         └────────┬────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼──┐    ┌────▼────┐   ┌───▼────┐
│Codebase│  │Code     │   │Autonomous│
│Context │  │Completion│  │Coder    │
└────────┘  └─────────┘   └─────────┘
```

---

## 💡 **Tips & Tricks**

### **Terminal:**

1. **Use tab for command history** (if supported)
2. **Ctrl+C to interrupt, NOT exit** (use `exit` command)
3. **Check status frequently** with `status` command
4. **Index once per session** - results are cached

### **Web:**

1. **Use quick actions** for common tasks
2. **Keep tab open** for real-time stats
3. **Multiple tabs** = multiple sessions
4. **Bookmark** for quick access

---

## 🐛 **Troubleshooting**

### **Terminal not starting:**

```bash
# Check dependencies
pip install -r requirements-app.txt

# Run with debug
python -v terminal_app.py
```

### **Web app not accessible:**

```bash
# Check if port 8000 is free
lsof -i :8000

# Try different port
# Edit web_app.py: uvicorn.run(..., port=3000)
```

### **Commands not working:**

```bash
# Make sure codebase is indexed first
rann> index

# Check you're in right workspace
rann> status
```

---

## 🎉 **That's It!**

Sekarang Papa punya **DUA cara** untuk interact dengan Rann Agent:

1. 💻 **Terminal** - For power users
2. 🌐 **Web** - For visual experience

**Both are equally powerful!** 🔥

Pilih yang Papa suka! 😎

---

**Repository:** https://github.com/rann-xyz/rann-agent

Made with 💪 by Papa Agis
