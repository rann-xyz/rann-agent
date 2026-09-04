<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RANN Agent - Autonomous AI Engineering Platform</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --parchment: #f5f4ed;
      --ivory: #faf9f5;
      --white: #ffffff;
      --sand: #e8e6dc;
      --near-black: #141413;
      --dark-surface: #30302e;
      --terracotta: #c96442;
      --coral: #d97757;
      --charcoal: #4d4c48;
      --olive: #5e5d59;
      --stone: #87867f;
      --warm-silver: #b0aea5;
      --border-cream: #f0eee6;
      --border-warm: #e8e6dc;
      --ring: #d1cfc5;
      --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
      --font-mono: 'JetBrains Mono', ui-monospace, monospace;
    }

    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    body {
      font-family: var(--font-sans);
      background: var(--parchment);
      color: var(--near-black);
      line-height: 1.6;
      min-height: 100vh;
    }

    /* ============ NAVIGATION ============ */
    nav {
      position: sticky;
      top: 0;
      z-index: 100;
      background: var(--parchment);
      border-bottom: 1px solid var(--border-cream);
      padding: 0 24px;
    }

    .nav-inner {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 64px;
    }

    .nav-logo {
      display: flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
      color: var(--near-black);
    }

    .nav-logo-icon {
      width: 36px;
      height: 36px;
      background: var(--near-black);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--sand);
      font-weight: 600;
      font-size: 14px;
    }

    .nav-logo-text {
      font-size: 20px;
      font-weight: 500;
      letter-spacing: -0.5px;
    }

    .nav-links {
      display: flex;
      gap: 32px;
      list-style: none;
    }

    .nav-links a {
      color: var(--olive);
      text-decoration: none;
      font-size: 15px;
      font-weight: 400;
      transition: color 0.2s;
    }

    .nav-links a:hover {
      color: var(--near-black);
    }

    .nav-cta {
      display: flex;
      gap: 12px;
    }

    .btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 20px;
      border-radius: 10px;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s;
      border: none;
      text-decoration: none;
    }

    .btn-ghost {
      background: transparent;
      color: var(--charcoal);
    }

    .btn-ghost:hover {
      background: var(--sand);
    }

    .btn-secondary {
      background: var(--sand);
      color: var(--charcoal);
    }

    .btn-secondary:hover {
      background: var(--border-warm);
    }

    .btn-primary {
      background: var(--terracotta);
      color: var(--ivory);
    }

    .btn-primary:hover {
      background: var(--coral);
    }

    .btn-dark {
      background: var(--near-black);
      color: var(--warm-silver);
      border: 1px solid var(--dark-surface);
    }

    .btn-dark:hover {
      background: var(--dark-surface);
    }

    /* ============ HERO SECTION ============ */
    .hero {
      max-width: 1200px;
      margin: 0 auto;
      padding: 80px 24px 120px;
      text-align: center;
    }

    .hero-badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 14px;
      background: var(--sand);
      border-radius: 20px;
      font-size: 13px;
      color: var(--charcoal);
      margin-bottom: 32px;
    }

    .hero-badge-dot {
      width: 6px;
      height: 6px;
      background: var(--terracotta);
      border-radius: 50%;
    }

    .hero h1 {
      font-size: clamp(36px, 6vw, 64px);
      font-weight: 500;
      line-height: 1.1;
      letter-spacing: -1px;
      margin-bottom: 24px;
      color: var(--near-black);
    }

    .hero h1 span {
      color: var(--terracotta);
    }

    .hero-subtitle {
      font-size: 20px;
      color: var(--olive);
      max-width: 600px;
      margin: 0 auto 40px;
      line-height: 1.6;
    }

    .hero-actions {
      display: flex;
      gap: 16px;
      justify-content: center;
      flex-wrap: wrap;
    }

    .hero-actions .btn {
      padding: 14px 28px;
      font-size: 16px;
    }

    /* ============ CHAT PREVIEW ============ */
    .chat-preview {
      max-width: 900px;
      margin: 0 auto 120px;
      padding: 0 24px;
    }

    .chat-window {
      background: var(--ivory);
      border: 1px solid var(--border-cream);
      border-radius: 16px;
      overflow: hidden;
      box-shadow: rgba(0,0,0,0.05) 0 4px 24px;
    }

    .chat-header {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 16px 20px;
      border-bottom: 1px solid var(--border-cream);
      background: var(--white);
    }

    .chat-header-dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: var(--terracotta);
    }

    .chat-header-title {
      font-size: 14px;
      font-weight: 500;
      color: var(--charcoal);
    }

    .chat-messages {
      padding: 24px;
      min-height: 300px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    .chat-message {
      display: flex;
      gap: 12px;
      max-width: 85%;
    }

    .chat-message.user {
      align-self: flex-end;
      flex-direction: row-reverse;
    }

    .chat-avatar {
      width: 32px;
      height: 32px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      font-weight: 600;
      flex-shrink: 0;
    }

    .chat-message.assistant .chat-avatar {
      background: var(--near-black);
      color: var(--sand);
    }

    .chat-message.user .chat-avatar {
      background: var(--sand);
      color: var(--charcoal);
    }

    .chat-bubble {
      padding: 12px 16px;
      border-radius: 12px;
      font-size: 15px;
      line-height: 1.5;
    }

    .chat-message.assistant .chat-bubble {
      background: var(--white);
      border: 1px solid var(--border-cream);
      color: var(--near-black);
    }

    .chat-message.user .chat-bubble {
      background: var(--near-black);
      color: var(--warm-silver);
    }

    .chat-input-area {
      padding: 16px 20px;
      border-top: 1px solid var(--border-cream);
      background: var(--white);
    }

    .chat-input-wrapper {
      display: flex;
      align-items: center;
      gap: 12px;
      background: var(--parchment);
      border: 1px solid var(--border-warm);
      border-radius: 12px;
      padding: 12px 16px;
    }

    .chat-input {
      flex: 1;
      border: none;
      background: transparent;
      font-size: 15px;
      font-family: var(--font-sans);
      color: var(--near-black);
      outline: none;
    }

    .chat-input::placeholder {
      color: var(--stone);
    }

    .chat-send {
      width: 32px;
      height: 32px;
      background: var(--terracotta);
      border: none;
      border-radius: 8px;
      color: var(--ivory);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.2s;
    }

    .chat-send:hover {
      background: var(--coral);
    }

    /* ============ FEATURES SECTION ============ */
    .features {
      background: var(--near-black);
      padding: 100px 24px;
    }

    .features-inner {
      max-width: 1200px;
      margin: 0 auto;
    }

    .section-label {
      font-size: 12px;
      font-weight: 500;
      letter-spacing: 0.5px;
      text-transform: uppercase;
      color: var(--stone);
      margin-bottom: 16px;
    }

    .features h2 {
      font-size: clamp(28px, 4vw, 44px);
      font-weight: 500;
      color: var(--ivory);
      margin-bottom: 60px;
      line-height: 1.2;
    }

    .features-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 24px;
    }

    .feature-card {
      background: var(--dark-surface);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 12px;
      padding: 28px;
      transition: border-color 0.2s;
    }

    .feature-card:hover {
      border-color: rgba(255,255,255,0.15);
    }

    .feature-icon {
      width: 40px;
      height: 40px;
      background: var(--terracotta);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 20px;
      font-size: 18px;
    }

    .feature-card h3 {
      font-size: 18px;
      font-weight: 500;
      color: var(--ivory);
      margin-bottom: 12px;
    }

    .feature-card p {
      font-size: 14px;
      color: var(--warm-silver);
      line-height: 1.6;
    }

    /* ============ CAPABILITIES SECTION ============ */
    .capabilities {
      max-width: 1200px;
      margin: 0 auto;
      padding: 100px 24px;
    }

    .capabilities-header {
      text-align: center;
      margin-bottom: 60px;
    }

    .capabilities h2 {
      font-size: clamp(28px, 4vw, 44px);
      font-weight: 500;
      color: var(--near-black);
      margin-bottom: 16px;
    }

    .capabilities-subtitle {
      font-size: 18px;
      color: var(--olive);
    }

    .capabilities-list {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 1px;
      background: var(--border-warm);
      border: 1px solid var(--border-warm);
      border-radius: 16px;
      overflow: hidden;
    }

    .capability-item {
      background: var(--ivory);
      padding: 28px 32px;
      display: flex;
      align-items: flex-start;
      gap: 20px;
    }

    .capability-check {
      width: 24px;
      height: 24px;
      background: var(--terracotta);
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--ivory);
      font-size: 14px;
      flex-shrink: 0;
      margin-top: 2px;
    }

    .capability-text h4 {
      font-size: 16px;
      font-weight: 500;
      color: var(--near-black);
      margin-bottom: 6px;
    }

    .capability-text p {
      font-size: 14px;
      color: var(--olive);
    }

    /* ============ CODE EXAMPLE ============ */
    .code-section {
      background: var(--near-black);
      padding: 80px 24px;
    }

    .code-inner {
      max-width: 900px;
      margin: 0 auto;
    }

    .code-section h2 {
      font-size: clamp(24px, 3vw, 36px);
      font-weight: 500;
      color: var(--ivory);
      text-align: center;
      margin-bottom: 40px;
    }

    .code-block {
      background: var(--dark-surface);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 12px;
      overflow: hidden;
    }

    .code-header {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 16px;
      border-bottom: 1px solid rgba(255,255,255,0.06);
    }

    .code-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }

    .code-dot.red { background: #ff5f57; }
    .code-dot.yellow { background: #ffbd2e; }
    .code-dot.green { background: #28c840; }

    .code-content {
      padding: 24px;
      font-family: var(--font-mono);
      font-size: 14px;
      line-height: 1.7;
      color: var(--warm-silver);
      overflow-x: auto;
    }

    .code-content .keyword { color: #c96442; }
    .code-content .string { color: #98c379; }
    .code-content .comment { color: #5c6370; }
    .code-content .function { color: #61afef; }

    /* ============ STATS SECTION ============ */
    .stats {
      max-width: 1200px;
      margin: 0 auto;
      padding: 80px 24px;
    }

    .stats-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 32px;
    }

    .stat-item {
      text-align: center;
      padding: 32px;
      background: var(--ivory);
      border: 1px solid var(--border-cream);
      border-radius: 12px;
    }

    .stat-number {
      font-size: 48px;
      font-weight: 500;
      color: var(--terracotta);
      line-height: 1;
      margin-bottom: 8px;
    }

    .stat-label {
      font-size: 15px;
      color: var(--olive);
    }

    /* ============ FOOTER ============ */
    footer {
      background: var(--near-black);
      padding: 60px 24px;
      border-top: 1px solid var(--dark-surface);
    }

    .footer-inner {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 24px;
    }

    .footer-logo {
      display: flex;
      align-items: center;
      gap: 12px;
      color: var(--ivory);
    }

    .footer-logo-icon {
      width: 32px;
      height: 32px;
      background: var(--terracotta);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--ivory);
      font-weight: 600;
      font-size: 12px;
    }

    .footer-logo-text {
      font-size: 18px;
      font-weight: 500;
    }

    .footer-links {
      display: flex;
      gap: 32px;
      list-style: none;
    }

    .footer-links a {
      color: var(--warm-silver);
      text-decoration: none;
      font-size: 14px;
      transition: color 0.2s;
    }

    .footer-links a:hover {
      color: var(--ivory);
    }

    .footer-copy {
      font-size: 13px;
      color: var(--stone);
    }

    /* ============ RESPONSIVE ============ */
    @media (max-width: 768px) {
      .nav-links { display: none; }
      .nav-cta .btn-ghost { display: none; }
      
      .hero { padding: 60px 24px 80px; }
      .hero h1 { font-size: 36px; }
      .hero-subtitle { font-size: 17px; }
      
      .stats-grid { grid-template-columns: repeat(2, 1fr); }
      
      .footer-inner { flex-direction: column; text-align: center; }
      .footer-links { flex-wrap: wrap; justify-content: center; }
    }

    @media (max-width: 480px) {
      .hero-actions { flex-direction: column; }
      .hero-actions .btn { width: 100%; justify-content: center; }
      .stats-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <!-- Navigation -->
  <nav>
    <div class="nav-inner">
      <a href="#" class="nav-logo">
        <div class="nav-logo-icon">RA</div>
        <span class="nav-logo-text">RANN Agent</span>
      </a>
      <ul class="nav-links">
        <li><a href="#features">Features</a></li>
        <li><a href="#capabilities">Capabilities</a></li>
        <li><a href="#code">Usage</a></li>
        <li><a href="https://github.com/rann-xyz/rann-agent" target="_blank">GitHub</a></li>
      </ul>
      <div class="nav-cta">
        <a href="#" class="btn btn-ghost">Docs</a>
        <a href="#" class="btn btn-primary">Get Started</a>
      </div>
    </div>
  </nav>

  <!-- Hero -->
  <section class="hero">
    <div class="hero-badge">
      <span class="hero-badge-dot"></span>
      Autonomous AI Engineering Platform
    </div>
    <h1>THE MODEL GENERATES<br><span>DECISIONS.</span> RANN CONTROLS<br>EXECUTION.</h1>
    <p class="hero-subtitle">
      Autonomous AI agent with 16-state machine, real terminal execution, evidence ledger, and structured memory. 
      Build, test, and deploy with confidence.
    </p>
    <div class="hero-actions">
      <a href="#" class="btn btn-primary">Try It Now →</a>
      <a href="#" class="btn btn-secondary">View on GitHub</a>
    </div>
  </section>

  <!-- Chat Preview -->
  <section class="chat-preview">
    <div class="chat-window">
      <div class="chat-header">
        <div class="chat-header-dot"></div>
        <span class="chat-header-title">RANN Agent - Interactive Chat</span>
      </div>
      <div class="chat-messages">
        <div class="chat-message assistant">
          <div class="chat-avatar">RA</div>
          <div class="chat-bubble">
            Hello! I'm RANN Agent. I can help you with coding tasks, file management, Git operations, and more. What would you like to do today?
          </div>
        </div>
        <div class="chat-message user">
          <div class="chat-avatar">You</div>
          <div class="chat-bubble">
            Create a Python file that calculates fibonacci numbers
          </div>
        </div>
        <div class="chat-message assistant">
          <div class="chat-avatar">RA</div>
          <div class="chat-bubble">
            I've created <code>fibonacci.py</code> with a function to calculate fibonacci numbers using dynamic programming. The file includes both recursive and iterative implementations with examples.
          </div>
        </div>
      </div>
      <div class="chat-input-area">
        <div class="chat-input-wrapper">
          <input type="text" class="chat-input" placeholder="Ask RANN Agent to help with your task...">
          <button class="chat-send">→</button>
        </div>
      </div>
    </div>
  </section>

  <!-- Features -->
  <section class="features" id="features">
    <div class="features-inner">
      <p class="section-label">Features</p>
      <h2>Built for serious engineering work</h2>
      <div class="features-grid">
        <div class="feature-card">
          <div class="feature-icon">⚡</div>
          <h3>16-State Machine</h3>
          <p>Explicit state transitions with QUEUED → ANALYZING → CONTEXT_READY → PLANNING → EXECUTING → VERIFYING → COMPLETED lifecycle.</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">🔒</div>
          <h3>Smart Safety</h3>
          <p>Command policy enforcement, approval gates, and sandboxed execution. Dangerous operations require explicit approval.</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">💾</div>
          <h3>Memory Architecture</h3>
          <p>Episodic, semantic, and project memory stores. Agent learns and remembers project conventions over time.</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">🧪</div>
          <h3>Evidence Ledger</h3>
          <p>Every action is traced and verified. Evidence-based proof that tasks completed correctly.</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">🔧</div>
          <h3>Tool Registry</h3>
          <p>Extensible tool system with terminal, file, git, search, and custom tools. New tools can be added easily.</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">📊</div>
          <h3>Budget Control</h3>
          <p>Token, time, cost, and turn budgets. Prevents runaway agent loops and manages resources effectively.</p>
        </div>
      </div>
    </div>
  </section>

  <!-- Capabilities -->
  <section class="capabilities" id="capabilities">
    <div class="capabilities-header">
      <h2>What RANN Agent can do</h2>
      <p class="capabilities-subtitle">From code generation to full project management</p>
    </div>
    <div class="capabilities-list">
      <div class="capability-item">
        <div class="capability-check">✓</div>
        <div class="capability-text">
          <h4>Code Generation & Editing</h4>
          <p>Write, edit, and refactor code in any language</p>
        </div>
      </div>
      <div class="capability-item">
        <div class="capability-check">✓</div>
        <div class="capability-text">
          <h4>File Operations</h4>
          <p>Create, read, modify, and organize files</p>
        </div>
      </div>
      <div class="capability-item">
        <div class="capability-check">✓</div>
        <div class="capability-text">
          <h4>Git Operations</h4>
          <p>Commit, branch, merge, and manage repositories</p>
        </div>
      </div>
      <div class="capability-item">
        <div class="capability-check">✓</div>
        <div class="capability-text">
          <h4>Terminal Execution</h4>
          <p>Run commands and scripts safely</p>
        </div>
      </div>
      <div class="capability-item">
        <div class="capability-check">✓</div>
        <div class="capability-text">
          <h4>Project Context</h4>
          <p>Learn and apply project conventions</p>
        </div>
      </div>
      <div class="capability-item">
        <div class="capability-check">✓</div>
        <div class="capability-text">
          <h4>Memory & Learning</h4>
          <p>Remember solutions and avoid repeating mistakes</p>
        </div>
      </div>
    </div>
  </section>

  <!-- Code Example -->
  <section class="code-section" id="code">
    <div class="code-inner">
      <h2>Simple to use</h2>
      <div class="code-block">
        <div class="code-header">
          <span class="code-dot red"></span>
          <span class="code-dot yellow"></span>
          <span class="code-dot green"></span>
        </div>
        <div class="code-content">
<span class="comment"># Install</span>
<span class="function">pip</span> install -e .

<span class="comment"># Run a task</span>
<span class="keyword">rann</span> run <span class="string">"create a hello world Python file"</span>

<span class="comment"># Interactive shell</span>
<span class="keyword">rann</span> shell

<span class="comment"># Check system</span>
<span class="keyword">rann</span> doctor

<span class="comment"># Change model</span>
<span class="keyword">rann</span> config set agent.llm.model claude-sonnet-4-20250514
        </div>
      </div>
    </div>
  </section>

  <!-- Stats -->
  <section class="stats">
    <div class="stats-grid">
      <div class="stat-item">
        <div class="stat-number">169</div>
        <div class="stat-label">Tests Passing</div>
      </div>
      <div class="stat-item">
        <div class="stat-number">121</div>
        <div class="stat-label">Modules</div>
      </div>
      <div class="stat-item">
        <div class="stat-number">16</div>
        <div class="stat-label">States</div>
      </div>
      <div class="stat-item">
        <div class="stat-number">35%</div>
        <div class="stat-label">Coverage</div>
      </div>
    </div>
  </section>

  <!-- Footer -->
  <footer>
    <div class="footer-inner">
      <div class="footer-logo">
        <div class="footer-logo-icon">RA</div>
        <span class="footer-logo-text">RANN Agent</span>
      </div>
      <ul class="footer-links">
        <li><a href="#">Documentation</a></li>
        <li><a href="https://github.com/rann-xyz/rann-agent">GitHub</a></li>
        <li><a href="#">Discord</a></li>
        <li><a href="#">Twitter</a></li>
      </ul>
      <p class="footer-copy">MIT License · Built with Hermes Agent</p>
    </div>
  </footer>
</body>
</html>