<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RANN Agent - Autonomous AI Engineering Platform</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
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

    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      font-family: var(--font-sans);
      background: var(--parchment);
      color: var(--near-black);
      line-height: 1.6;
      min-height: 100vh;
    }

    /* Navigation */
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
      justify-content: space-between;
      align-items: center;
      height: 64px;
    }

    .nav-logo {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .nav-logo-icon {
      width: 36px;
      height: 36px;
      background: var(--terracotta);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      color: var(--ivory);
      font-size: 14px;
    }

    .nav-logo-text {
      font-weight: 500;
      font-size: 18px;
      color: var(--near-black);
    }

    .nav-links {
      display: flex;
      list-style: none;
      gap: 32px;
    }

    .nav-links a {
      color: var(--olive);
      text-decoration: none;
      font-size: 14px;
      transition: color 0.2s;
    }

    .nav-links a:hover { color: var(--near-black); }

    .nav-cta {
      display: flex;
      gap: 12px;
    }

    .btn {
      padding: 10px 20px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.2s;
      border: none;
      font-family: var(--font-sans);
    }

    .btn-secondary {
      background: transparent;
      color: var(--near-black);
    }

    .btn-secondary:hover { background: var(--sand); }

    .btn-primary {
      background: var(--near-black);
      color: var(--ivory);
    }

    .btn-primary:hover { background: var(--charcoal); }

    /* Hero */
    .hero {
      max-width: 900px;
      margin: 0 auto;
      padding: 100px 24px;
      text-align: center;
    }

    .hero-eyebrow {
      font-size: 14px;
      color: var(--terracotta);
      font-weight: 500;
      margin-bottom: 16px;
      letter-spacing: 0.5px;
    }

    .hero h1 {
      font-size: clamp(36px, 6vw, 56px);
      font-weight: 500;
      line-height: 1.15;
      color: var(--near-black);
      margin-bottom: 24px;
    }

    .hero-subtitle {
      font-size: 18px;
      color: var(--olive);
      max-width: 600px;
      margin: 0 auto 40px;
    }

    .hero-cta {
      display: flex;
      gap: 12px;
      justify-content: center;
    }

    /* Features */
    .features {
      background: var(--near-black);
      padding: 80px 24px;
    }

    .features-inner {
      max-width: 1200px;
      margin: 0 auto;
    }

    .section-label {
      font-size: 13px;
      color: var(--warm-silver);
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-bottom: 12px;
    }

    .section-title {
      font-size: clamp(28px, 4vw, 40px);
      font-weight: 500;
      color: var(--ivory);
      margin-bottom: 48px;
    }

    .features-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 24px;
    }

    .feature-card {
      background: var(--dark-surface);
      border-radius: 12px;
      padding: 28px;
    }

    .feature-icon {
      width: 44px;
      height: 44px;
      background: var(--terracotta);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 20px;
      font-size: 20px;
    }

    .feature-card h3 {
      font-size: 18px;
      font-weight: 500;
      color: var(--ivory);
      margin-bottom: 10px;
    }

    .feature-card p {
      font-size: 14px;
      color: var(--warm-silver);
      line-height: 1.6;
    }

    /* Code Block */
    .code-section {
      padding: 80px 24px;
    }

    .code-inner {
      max-width: 900px;
      margin: 0 auto;
    }

    .code-block {
      background: var(--near-black);
      border-radius: 12px;
      padding: 24px;
      margin-top: 32px;
      overflow-x: auto;
    }

    .code-block pre {
      color: var(--ivory);
      font-family: var(--font-mono);
      font-size: 14px;
      line-height: 1.7;
    }

    .code-block .prompt { color: var(--terracotta); }
    .code-block .comment { color: var(--stone); }
    .code-block .command { color: var(--green); }

    /* Stats */
    .stats {
      background: var(--ivory);
      padding: 60px 24px;
      border-top: 1px solid var(--border-cream);
      border-bottom: 1px solid var(--border-cream);
    }

    .stats-inner {
      max-width: 1000px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 32px;
      text-align: center;
    }

    .stat-number {
      font-size: clamp(32px, 5vw, 48px);
      font-weight: 600;
      color: var(--near-black);
      font-family: var(--font-mono);
    }

    .stat-label {
      font-size: 14px;
      color: var(--olive);
      margin-top: 4px;
    }

    /* Settings */
    .settings {
      padding: 80px 24px;
      background: var(--parchment);
    }

    .settings-inner {
      max-width: 1200px;
      margin: 0 auto;
    }

    .settings-header {
      text-align: center;
      margin-bottom: 48px;
    }

    .settings-header h2 {
      font-size: clamp(28px, 4vw, 40px);
      font-weight: 500;
      color: var(--near-black);
      margin-bottom: 12px;
    }

    .settings-header p {
      font-size: 18px;
      color: var(--olive);
    }

    .settings-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 24px;
    }

    .settings-card {
      background: var(--ivory);
      border: 1px solid var(--border-cream);
      border-radius: 12px;
      padding: 24px;
    }

    .settings-card h3 {
      font-size: 16px;
      font-weight: 500;
      color: var(--near-black);
      margin-bottom: 16px;
    }

    .setting-group {
      margin-bottom: 14px;
    }

    .setting-group label {
      display: block;
      font-size: 13px;
      color: var(--olive);
      margin-bottom: 6px;
    }

    .setting-group select,
    .setting-group input[type="number"] {
      width: 100%;
      padding: 10px 12px;
      border: 1px solid var(--border-warm);
      border-radius: 8px;
      font-size: 14px;
      font-family: var(--font-sans);
      background: var(--white);
      color: var(--near-black);
    }

    .settings-card-dark {
      background: var(--near-black);
      border-color: var(--dark-surface);
    }

    .settings-card-dark h3 {
      color: var(--ivory);
    }

    .config-display {
      background: var(--dark-surface);
      border-radius: 8px;
      padding: 16px;
    }

    .config-item {
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      border-bottom: 1px solid rgba(255,255,255,0.06);
      font-size: 13px;
    }

    .config-item:last-child { border-bottom: none; }
    .config-label { color: var(--warm-silver); }
    .config-value { color: var(--ivory); font-family: var(--font-mono); }

    /* Chat */
    .chat-section {
      background: var(--near-black);
      border-radius: 16px;
      padding: 28px;
      margin-top: 24px;
    }

    .chat-section h3 {
      color: var(--ivory);
      font-size: 16px;
      font-weight: 500;
      margin-bottom: 16px;
    }

    .chat-container {
      background: var(--dark-surface);
      border-radius: 12px;
      overflow: hidden;
    }

    .chat-messages {
      min-height: 200px;
      max-height: 350px;
      overflow-y: auto;
      padding: 20px;
    }

    .chat-message {
      display: flex;
      gap: 12px;
      margin-bottom: 16px;
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
      background: var(--terracotta);
      color: var(--ivory);
    }

    .chat-message.user .chat-avatar {
      background: var(--sand);
      color: var(--near-black);
    }

    .chat-bubble {
      padding: 12px 16px;
      border-radius: 12px;
      font-size: 14px;
      line-height: 1.5;
    }

    .chat-message.assistant .chat-bubble {
      background: var(--near-black);
      color: var(--ivory);
    }

    .chat-message.user .chat-bubble {
      background: var(--terracotta);
      color: var(--ivory);
    }

    .chat-input-area {
      padding: 16px;
      border-top: 1px solid var(--dark-surface);
    }

    .chat-input-wrapper {
      display: flex;
      gap: 12px;
    }

    .chat-input {
      flex: 1;
      padding: 12px 16px;
      border: 1px solid var(--dark-surface);
      border-radius: 8px;
      font-size: 14px;
      font-family: var(--font-sans);
      background: var(--near-black);
      color: var(--ivory);
    }

    .chat-input::placeholder { color: var(--stone); }

    .chat-send {
      padding: 12px 20px;
      background: var(--terracotta);
      color: var(--ivory);
      border: none;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      font-family: var(--font-sans);
    }

    .chat-send:hover { background: var(--coral); }

    /* Footer */
    footer {
      background: var(--near-black);
      padding: 40px 24px;
      margin-top: 40px;
    }

    .footer-inner {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 20px;
    }

    .footer-logo {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .footer-logo-icon {
      width: 32px;
      height: 32px;
      background: var(--terracotta);
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      color: var(--ivory);
      font-size: 12px;
    }

    .footer-logo-text {
      color: var(--ivory);
      font-weight: 500;
    }

    .footer-links {
      display: flex;
      list-style: none;
      gap: 24px;
    }

    .footer-links a {
      color: var(--warm-silver);
      text-decoration: none;
      font-size: 14px;
    }

    .footer-links a:hover { color: var(--ivory); }

    .footer-copy {
      color: var(--stone);
      font-size: 13px;
      width: 100%;
      text-align: center;
      margin-top: 20px;
    }

    /* Responsive */
    @media (max-width: 768px) {
      .nav-links { display: none; }
      .stats-inner { grid-template-columns: repeat(2, 1fr); }
      .hero-cta { flex-direction: column; }
      .footer-inner { flex-direction: column; text-align: center; }
    }
  </style>
</head>
<body>
  <nav>
    <div class="nav-inner">
      <div class="nav-logo">
        <div class="nav-logo-icon">RA</div>
        <span class="nav-logo-text">RANN Agent</span>
      </div>
      <ul class="nav-links">
        <li><a href="#features">Features</a></li>
        <li><a href="#code">Usage</a></li>
        <li><a href="#settings">Settings</a></li>
        <li><a href="https://github.com/rann-xyz/rann-agent" target="_blank">GitHub</a></li>
      </ul>
      <div class="nav-cta">
        <a href="#settings" class="btn btn-secondary">Configure</a>
        <a href="https://github.com/rann-xyz/rann-agent" class="btn btn-primary" target="_blank">Get Started</a>
      </div>
    </div>
  </nav>

  <section class="hero">
    <div class="hero-eyebrow">AUTONOMOUS AI ENGINEERING</div>
    <h1>THE MODEL GENERATES DECISIONS.<br>RANN CONTROLS EXECUTION.</h1>
    <p class="hero-subtitle">An autonomous AI agent that plans, executes, and verifies tasks with safety controls, memory, and continuous learning.</p>
    <div class="hero-cta">
      <a href="https://github.com/rann-xyz/rann-agent" class="btn btn-primary" target="_blank">Install RANN</a>
      <a href="#settings" class="btn btn-secondary">Configure Model</a>
    </div>
  </section>

  <section class="features" id="features">
    <div class="features-inner">
      <div class="section-label">CAPABILITIES</div>
      <h2 class="section-title">Built for Complex Tasks</h2>
      <div class="features-grid">
        <div class="feature-card">
          <div class="feature-icon">&#128161;</div>
          <h3>16-State Machine</h3>
          <p>Advanced state management with QUEUED, ANALYZING, PLANNING, EXECUTING, VERIFYING, and more for robust task handling.</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">&#128737;</div>
          <h3>Safety First</h3>
          <p>Smart command approval, dangerous pattern detection, budget limits, and audit logging for secure operation.</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">&#128203;</div>
          <h3>Persistent Memory</h3>
          <p>Semantic, episodic, and working memory stores that persist across sessions for context awareness.</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">&#127918;</div>
          <h3>Self-Improvement</h3>
          <p>Learning engine that learns from successes and failures, with self-correction capabilities.</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">&#128270;</div>
          <h3>Web Research</h3>
          <p>Real-time web search integration for up-to-date information and source verification.</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">&#128221;</div>
          <h3>Self-Coding</h3>
          <p>Agent can modify its own code within safe boundaries with backup and rollback support.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="code-section" id="code">
    <div class="code-inner">
      <div class="section-label">GET STARTED</div>
      <h2 class="section-title">Simple to Use</h2>
      <div class="code-block">
        <pre><span class="prompt">$</span> <span class="command">pip install rann-agent</span>

<span class="prompt">$</span> <span class="command">rann doctor</span>                    <span class="comment"># Check system health</span>
<span class="prompt">$</span> <span class="command">rann config get</span>                 <span class="comment"># View current config</span>
<span class="prompt">$</span> <span class="command">rann run "create a README.md"</span>  <span class="comment"># Execute task</span>
<span class="prompt">$</span> <span class="command">rann shell</span>                     <span class="comment"># Interactive chat</span>
<span class="prompt">$</span> <span class="command">rann serve</span>                     <span class="comment"># Start web interface</span></pre>
      </div>
    </div>
  </section>

  <section class="stats">
    <div class="stats-inner">
      <div>
        <div class="stat-number">169</div>
        <div class="stat-label">Tests Passing</div>
      </div>
      <div>
        <div class="stat-number">121</div>
        <div class="stat-label">Python Modules</div>
      </div>
      <div>
        <div class="stat-number">16</div>
        <div class="stat-label">Agent States</div>
      </div>
      <div>
        <div class="stat-number">34%</div>
        <div class="stat-label">Code Coverage</div>
      </div>
    </div>
  </section>

  <section class="settings" id="settings">
    <div class="settings-inner">
      <div class="settings-header">
        <h2>Settings</h2>
        <p>Configure your RANN Agent</p>
      </div>
      
      <div class="settings-grid">
        <div class="settings-card">
          <h3>Model Configuration</h3>
          <div class="setting-group">
            <label>Provider</label>
            <select id="provider" onchange="updateModels()">
              <option value="xkiro">xkiro (Free)</option>
              <option value="anthropic">Anthropic</option>
              <option value="openai">OpenAI</option>
            </select>
          </div>
          <div class="setting-group">
            <label>Model</label>
            <select id="model">
              <option value="minimax/minimax-m2.7-highspeed:free">minimax/m2.7-highspeed (Free)</option>
              <option value="claude-sonnet-4-20250514">Claude Sonnet 4</option>
              <option value="gpt-4o">GPT-4o</option>
            </select>
          </div>
        </div>

        <div class="settings-card">
          <h3>Agent Behavior</h3>
          <div class="setting-group">
            <label>Max Iterations</label>
            <input type="number" id="max-iterations" value="50" min="1" max="200">
          </div>
          <div class="setting-group">
            <label>Max Tokens</label>
            <input type="number" id="max-tokens" value="50000" min="1000" max="200000">
          </div>
        </div>

        <div class="settings-card settings-card-dark">
          <h3>Current Configuration</h3>
          <div class="config-display">
            <div class="config-item">
              <span class="config-label">Provider</span>
              <span class="config-value" id="cfg-provider">xkiro</span>
            </div>
            <div class="config-item">
              <span class="config-label">Model</span>
              <span class="config-value" id="cfg-model">minimax/m2.7</span>
            </div>
            <div class="config-item">
              <span class="config-label">Max Iterations</span>
              <span class="config-value" id="cfg-iterations">50</span>
            </div>
            <div class="config-item">
              <span class="config-label">Max Tokens</span>
              <span class="config-value" id="cfg-tokens">50000</span>
            </div>
          </div>
        </div>

        <div class="settings-card">
          <h3>Enabled Tools</h3>
          <div style="display: grid; gap: 8px; font-size: 14px;">
            <label style="display: flex; align-items: center; gap: 8px;">
              <input type="checkbox" checked disabled> Terminal
            </label>
            <label style="display: flex; align-items: center; gap: 8px;">
              <input type="checkbox" checked> Read File
            </label>
            <label style="display: flex; align-items: center; gap: 8px;">
              <input type="checkbox" checked> Write File
            </label>
            <label style="display: flex; align-items: center; gap: 8px;">
              <input type="checkbox" checked> Web Search
            </label>
            <label style="display: flex; align-items: center; gap: 8px;">
              <input type="checkbox" checked> Git
            </label>
          </div>
        </div>
      </div>

      <div class="chat-section">
        <h3>Interactive Chat</h3>
        <div class="chat-container">
          <div class="chat-messages" id="chat-messages">
            <div class="chat-message assistant">
              <div class="chat-avatar">RA</div>
              <div class="chat-bubble">Hello! I am RANN Agent. How can I help you today?</div>
            </div>
          </div>
          <div class="chat-input-area">
            <div class="chat-input-wrapper">
              <input type="text" class="chat-input" id="chat-input" placeholder="Ask me anything..." onkeypress="if(event.key==='Enter')sendChat()">
              <button class="chat-send" onclick="sendChat()">Send</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <footer>
    <div class="footer-inner">
      <div class="footer-logo">
        <div class="footer-logo-icon">RA</div>
        <span class="footer-logo-text">RANN Agent</span>
      </div>
      <ul class="footer-links">
        <li><a href="https://github.com/rann-xyz/rann-agent" target="_blank">GitHub</a></li>
        <li><a href="#settings">Settings</a></li>
      </ul>
      <p class="footer-copy">MIT License - Built with Hermes Agent</p>
    </div>
  </footer>

  <script>
    function updateModels() {
      var provider = document.getElementById('provider').value;
      var modelSelect = document.getElementById('model');
      var models = {
        xkiro: [
          { value: 'minimax/minimax-m2.7-highspeed:free', label: 'minimax/m2.7-highspeed (Free)' }
        ],
        anthropic: [
          { value: 'claude-sonnet-4-20250514', label: 'Claude Sonnet 4' },
          { value: 'claude-opus-4-20250514', label: 'Claude Opus 4' }
        ],
        openai: [
          { value: 'gpt-4o', label: 'GPT-4o' },
          { value: 'gpt-4o-mini', label: 'GPT-4o Mini' }
        ]
      };
      modelSelect.innerHTML = models[provider].map(function(m) {
        return '<option value="' + m.value + '">' + m.label + '</option>';
      }).join('');
    }

    function addChatMessage(role, content) {
      var messagesDiv = document.getElementById('chat-messages');
      var avatar = role === 'user' ? 'You' : 'RA';
      var messageDiv = document.createElement('div');
      messageDiv.className = 'chat-message ' + (role === 'user' ? 'user' : 'assistant');
      messageDiv.innerHTML = 
        '<div class="chat-avatar">' + avatar + '</div>' +
        '<div class="chat-bubble">' + content + '</div>';
      messagesDiv.appendChild(messageDiv);
      messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    function sendChat() {
      var input = document.getElementById('chat-input');
      var message = input.value.trim();
      if (!message) return;
      
      addChatMessage('user', message);
      input.value = '';
      
      setTimeout(function() {
        var responses = [
          "I am RANN Agent, an autonomous AI engineering platform. I can help you with coding tasks, file operations, Git management, and more.",
          "I have analyzed your request. Use `rann run` command to execute tasks with me.",
          "My capabilities include code generation, debugging, file management, web research, and continuous learning."
        ];
        var response = responses[Math.floor(Math.random() * responses.length)];
        addChatMessage('assistant', response);
      }, 800);
    }

    // Load saved settings
    window.onload = function() {
      var saved = localStorage.getItem('rann_settings');
      if (saved) {
        var settings = JSON.parse(saved);
        document.getElementById('provider').value = settings.provider || 'xkiro';
        document.getElementById('max-iterations').value = settings.maxIterations || '50';
        document.getElementById('max-tokens').value = settings.maxTokens || '50000';
        updateModels();
      }
    };
  </script>
</body>
</html>