import React, { useState, useEffect, useRef } from 'react';
import './App.css';

// Custom inline SVG icons
const MoonIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
);

const SunIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="4.22" x2="19.78" y2="5.64"></line></svg>
);

const SendIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
);

const CloseIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
);

const FileIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
);

const InfoIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
);

const API_BASE = "http://127.0.0.1:8000";

const SAMPLE_QUERIES = [
  {
    title: "Foreign Currency Accounts",
    query: "What are the rules for foreign currency business value accounts?"
  },
  {
    title: "Public Holidays 2024",
    query: "What are the guidelines for public holidays in BPRD circulars?"
  },
  {
    title: "Circular No. 17 of 2024",
    query: "Show me details about BPRD Circular No. 17 of 2024."
  },
  {
    title: "Prudential Regulations",
    query: "What are SBP requirements regarding prudential asset classification?"
  }
];

function App() {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedChunk, setSelectedChunk] = useState(null);
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  
  // RAG Configurations
  const [topK, setTopK] = useState(5);
  const [retrievalMode, setRetrievalMode] = useState('hybrid');
  const [selectedDept, setSelectedDept] = useState('');

  // Diagnostics Toggles (mapped by message index)
  const [openedDiagnostics, setOpenedDiagnostics] = useState({});

  // Backend connection status
  const [status, setStatus] = useState({
    connected: false,
    lmStudioConnected: false,
    retrieverLoaded: false
  });

  const chatEndRef = useRef(null);

  // Sync theme to document body
  useEffect(() => {
    if (darkMode) {
      document.body.classList.add('dark-theme');
    } else {
      document.body.classList.remove('dark-theme');
    }
  }, [darkMode]);

  // Check backend health on load and periodically
  const checkHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/status`);
      if (res.ok) {
        const data = await res.json();
        setStatus({
          connected: true,
          lmStudioConnected: data.lm_studio_connected,
          retrieverLoaded: data.retriever_loaded
        });
      } else {
        setStatus({ connected: false, lmStudioConnected: false, retrieverLoaded: false });
      }
    } catch (e) {
      setStatus({ connected: false, lmStudioConnected: false, retrieverLoaded: false });
    }
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll to chat bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const toggleDiagnostic = (idx) => {
    setOpenedDiagnostics(prev => ({
      ...prev,
      [idx]: !prev[idx]
    }));
  };

  const handleSend = async (e, customQuery = null) => {
    e?.preventDefault();
    const activeQuery = (customQuery || query).trim();
    if (!activeQuery || loading) return;

    if (!customQuery) {
      setQuery('');
    }

    // Add user message
    const userMsg = { role: 'user', content: activeQuery };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: activeQuery,
          top_k: parseInt(topK),
          retrieval_mode: retrievalMode,
          department: selectedDept || null
        })
      });

      if (!res.ok) {
        throw new Error(`API returned status ${res.status}`);
      }

      const data = await res.json();

      // Add assistant response
      const assistantMsg = {
        role: 'assistant',
        content: data.answer,
        chunks: data.chunks,
        diagnostics: {
          answered: data.answered,
          sufficiencyChecked: data.sufficiency_checked,
          sufficiencyReasoning: data.sufficiency_reasoning,
          citationIssues: data.citation_issues,
          isMock: data.is_mock,
          retrievalMode,
          topK
        }
      };

      setMessages(prev => [...prev, assistantMsg]);
    } catch (error) {
      console.error(error);
      setMessages(prev => [
        ...prev,
        {
          role: 'system',
          content: `Error: Unable to connect to SAG service on ${API_BASE}. Please ensure the python server is running.`
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  // Render text and replace [Citation] with interactive tags
  const renderMessageText = (text, chunks) => {
    if (!text) return "";
    
    const regex = /\[([^\]]+)\]/g;
    const parts = [];
    let lastIndex = 0;
    let match;
    
    while ((match = regex.exec(text)) !== null) {
      const matchIndex = match.index;
      const fullMatch = match[0];
      const citationContent = match[1];
      
      if (matchIndex > lastIndex) {
        parts.push(text.substring(lastIndex, matchIndex));
      }
      
      // Match citation to returned chunks
      const normalizedCit = citationContent.toLowerCase().trim();
      const matchedChunk = chunks?.find(c => {
        const cn = c.circular_number.toLowerCase().trim();
        const dt = c.date.toLowerCase().trim();
        return normalizedCit.includes(cn) || cn.includes(normalizedCit) || (normalizedCit.includes(dt) && cn.includes("letter"));
      }) || chunks?.[0]; // Default fallback if chunks exist

      if (matchedChunk) {
        parts.push(
          <span 
            key={matchIndex} 
            className="citation-link" 
            onClick={() => {
              setSelectedChunk(matchedChunk);
              setIsInspectorOpen(true);
            }}
            title="Click to view source circular"
          >
            {fullMatch}
          </span>
        );
      } else {
        parts.push(fullMatch);
      }
      
      lastIndex = regex.lastIndex;
    }
    
    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }
    
    return parts.length > 0 ? parts : text;
  };

  const formatParagraphs = (text, chunks) => {
    if (!text) return null;
    return text.split('\n\n').map((para, i) => (
      <p key={i} style={{ marginBottom: '12px' }}>
        {renderMessageText(para, chunks)}
      </p>
    ));
  };

  return (
    <div className={`app-container ${isInspectorOpen ? 'inspector-open' : ''}`}>
      {/* Sidebar Panel */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo-icon">S</div>
          <div>
            <h1 className="logo-text">SBP GPT</h1>
            <div className="logo-sub">Compliance Advisory</div>
          </div>
        </div>

        <div className="sidebar-content">
          <div>
            <div className="sidebar-section-title">Regulatory Queries</div>
            <div className="sample-queries-list">
              {SAMPLE_QUERIES.map((sq, i) => (
                <button 
                  key={i} 
                  className="query-card"
                  onClick={(e) => handleSend(e, sq.query)}
                  disabled={loading}
                >
                  <strong>{sq.title}</strong>
                  <div style={{ fontSize: '11px', marginTop: '4px', opacity: 0.7, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {sq.query}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="sidebar-footer">
          <button className="theme-btn" onClick={() => setDarkMode(!darkMode)}>
            {darkMode ? <SunIcon /> : <MoonIcon />}
            {darkMode ? 'Light Theme' : 'Dark Theme'}
          </button>
        </div>
      </aside>

      {/* Main Chat Workspace */}
      <main className="main-workspace">
        <header className="workspace-header">
          <div className="header-title-container">
            <h2>State Bank of Pakistan (SBP) Compliance Advisory</h2>
          </div>
          
          <div className="header-status-badges">
            <div className={`status-badge ${status.connected ? 'online' : 'offline'}`}>
              <div className="status-indicator" />
              API: {status.connected ? 'Connected' : 'Offline'}
            </div>
            <div className={`status-badge ${status.lmStudioConnected ? 'online' : 'offline'}`}>
              <div className="status-indicator" />
              LLM: {status.lmStudioConnected ? 'Ready (Local)' : 'Offline (Sim Mode)'}
            </div>
          </div>
        </header>

        {/* Messages List Area */}
        <div className="chat-console">
          {messages.length === 0 ? (
            <div className="welcome-screen">
              <div className="welcome-logo">🏛️</div>
              <h3 className="welcome-title">SBP Compliance RAG Console</h3>
              <p className="welcome-desc">
                Query regulatory circulars from the State Bank of Pakistan. This system retrieves matching documents using hybrid search and synthesizes answers cited back to official documents.
              </p>
              <p className="welcome-desc" style={{ fontSize: '13px', opacity: 0.8, fontStyle: 'italic' }}>
                Select a template query on the left or type your compliance question below to get started.
              </p>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={idx} className={`message-bubble ${msg.role}`}>
                <div className="message-sender">{msg.role === 'user' ? 'Compliance Officer' : msg.role === 'system' ? 'System Notification' : 'RAG Assistant'}</div>
                <div className="message-text">
                  {msg.role === 'assistant' ? formatParagraphs(msg.content, msg.chunks) : msg.content}
                </div>

                {/* Diagnostic Panel for Assistant Answers */}
                {msg.role === 'assistant' && msg.diagnostics && (
                  <div className="rag-diagnostics">
                    <button className="diagnostic-toggle" onClick={() => toggleDiagnostic(idx)}>
                      <InfoIcon />
                      {openedDiagnostics[idx] ? 'Hide RAG Diagnostics' : 'Show RAG Diagnostics'}
                    </button>
                    {openedDiagnostics[idx] && (
                      <div className="diagnostic-content">
                        <div className="diagnostic-row">
                          <span className="diagnostic-label">Mode / Top-K:</span>
                          <span className="diagnostic-value" style={{ textTransform: 'capitalize' }}>
                            {msg.diagnostics.retrievalMode} retriever (k={msg.diagnostics.topK})
                          </span>
                        </div>
                        <div className="diagnostic-row">
                          <span className="diagnostic-label">Sufficiency Gate:</span>
                          <span className={`diagnostic-value ${msg.diagnostics.answered ? 'success' : 'warning'}`}>
                            {msg.diagnostics.answered ? 'PASSED (SUFFICIENT)' : 'FAILED (INSUFFICIENT)'}
                          </span>
                        </div>
                        {msg.diagnostics.sufficiencyReasoning && (
                          <div className="diagnostic-reasoning">
                            Reasoning: {msg.diagnostics.sufficiencyReasoning}
                          </div>
                        )}
                        <div className="diagnostic-row">
                          <span className="diagnostic-label">Citation Integrity:</span>
                          <span className={`diagnostic-value ${msg.diagnostics.citationIssues.length === 0 ? 'success' : 'warning'}`}>
                            {msg.diagnostics.citationIssues.length === 0 ? 'All citations verified' : `${msg.diagnostics.citationIssues.length} issues flagged`}
                          </span>
                        </div>
                        {msg.diagnostics.isMock && (
                          <div className="diagnostic-row" style={{ color: 'var(--warning)', fontSize: '11px', fontWeight: 'bold' }}>
                            ⚠️ Running in Simulated Fallback Mode (LM Studio Server Down)
                          </div>
                        )}

                        <div style={{ fontSize: '11px', fontWeight: 'bold', marginTop: '6px', color: 'var(--text-secondary)' }}>
                          Retrieved Circular Passages (Click to Inspect):
                        </div>
                        <div className="retrieved-docs-mini">
                          {msg.chunks?.map((c, cIdx) => (
                            <div 
                              key={cIdx} 
                              className="doc-mini-card"
                              onClick={() => {
                                setSelectedChunk(c);
                                setIsInspectorOpen(true);
                              }}
                            >
                              <div className="doc-mini-info">
                                <span className="doc-mini-title">{c.circular_number || 'Circular'}</span>
                                <span className="doc-mini-meta">{c.title || 'Untitled Circular'}</span>
                              </div>
                              <span style={{ fontSize: '10px', color: 'var(--secondary)', fontWeight: 700 }}>
                                Score: {c.score}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))
          )}

          {loading && (
            <div className="message-bubble assistant">
              <div className="message-sender">RAG Assistant</div>
              <div className="typing-indicator">
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input & Configurations area */}
        <div className="input-area">
          <form className="input-row" onSubmit={handleSend}>
            <input
              type="text"
              className="chat-input"
              placeholder="Ask a compliance or banking query (e.g. 'rules for foreign currency accounts')..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={loading}
            />
            <button className="send-btn" type="submit" disabled={loading || !query.trim()}>
              <SendIcon />
              Submit
            </button>
          </form>

          {/* Config values bar */}
          <div className="config-bar">
            <div className="config-group">
              <div className="config-item">
                <span className="config-label">Retrieval Mode:</span>
                <select 
                  className="config-select"
                  value={retrievalMode}
                  onChange={(e) => setRetrievalMode(e.target.value)}
                >
                  <option value="hybrid">Dense + BM25 Hybrid Fusion</option>
                  <option value="bm25">BM25 Keyword Only</option>
                </select>
              </div>

              <div className="config-item">
                <span className="config-label">Top-K Docs:</span>
                <select 
                  className="config-select"
                  value={topK}
                  onChange={(e) => setTopK(e.target.value)}
                >
                  <option value="3">3 Documents</option>
                  <option value="5">5 Documents</option>
                  <option value="7">7 Documents</option>
                  <option value="10">10 Documents</option>
                </select>
              </div>

              <div className="config-item">
                <span className="config-label">Dept Filter:</span>
                <select 
                  className="config-select"
                  value={selectedDept}
                  onChange={(e) => setSelectedDept(e.target.value)}
                >
                  <option value="">All Departments</option>
                  <option value="BPRD">BPRD (Policy & Regulations)</option>
                  <option value="BSD">BSD (Supervision)</option>
                  <option value="DMMD">DMMD (Monetary Management)</option>
                  <option value="ACD">ACD (Agricultural Credit)</option>
                </select>
              </div>
            </div>

            <div style={{ fontSize: '11px', color: 'var(--text-light)', fontWeight: 600 }}>
              SBP GPT Compliance Advisor v1.0
            </div>
          </div>
        </div>
      </main>

      {/* Right sliding inspector side panel */}
      {isInspectorOpen && (
        <aside className="inspector-panel">
          <div className="inspector-header">
            <div className="inspector-title">
              <FileIcon />
              Circular Source Text
            </div>
            <button className="close-inspector-btn" onClick={() => setIsInspectorOpen(false)}>
              <CloseIcon />
            </button>
          </div>

          <div className="inspector-content">
            {selectedChunk ? (
              <>
                <div className="inspector-meta-grid">
                  <div className="meta-item">
                    <span className="meta-label">Circular No</span>
                    <span className="meta-value">{selectedChunk.circular_number || 'N/A'}</span>
                  </div>
                  <div className="meta-item">
                    <span className="meta-label">Date</span>
                    <span className="meta-value">{selectedChunk.date || 'N/A'}</span>
                  </div>
                  <div className="meta-item">
                    <span className="meta-label">Department</span>
                    <span className="meta-value">{selectedChunk.department || 'N/A'}</span>
                  </div>
                  <div className="meta-item">
                    <span className="meta-label">Retrieval Score</span>
                    <span className="meta-value" style={{ color: 'var(--secondary)' }}>{selectedChunk.score || '0.0'}</span>
                  </div>
                </div>

                <div>
                  <div className="meta-label" style={{ marginBottom: '6px' }}>Circular Title</div>
                  <h3 className="inspector-doc-title">{selectedChunk.title || 'Untitled Passage'}</h3>
                </div>

                <div>
                  <div className="meta-label" style={{ marginBottom: '6px' }}>Circular Text Chunk</div>
                  <div className="inspector-doc-text">{selectedChunk.text}</div>
                </div>
              </>
            ) : (
              <div className="inspector-empty-state">
                <div className="inspector-empty-icon">📂</div>
                <h3>No Document Inspected</h3>
                <p style={{ fontSize: '13px' }}>Click on a citation badge in the chat history or in the diagnostics panel to read the full source text.</p>
              </div>
            )}
          </div>
        </aside>
      )}
    </div>
  );
}

export default App;
