import { useEffect, useState } from 'react';
import { ArrowLeft, ChevronDown, ChevronUp, Database } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function LogsScreen() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    async function fetchLogs() {
      try {
        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        const res = await fetch(`${apiUrl}/admin/logs`);
        if (!res.ok) throw new Error("Failed to fetch logs");
        const data = await res.json();
        setLogs(data.logs || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    fetchLogs();
  }, []);

  const toggleExpand = (idx) => {
    setExpandedId(expandedId === idx ? null : idx);
  };

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center h-full min-h-screen">
        <div className="w-12 h-12 border-4 border-accent border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-surface font-mono animate-pulse">Loading Logs...</p>
      </div>
    );
  }

  return (
    <div className="flex-1 w-full max-w-6xl mx-auto p-4 sm:p-6 lg:p-8 pb-20">
      <button 
        onClick={() => navigate('/admin/interviews')} 
        className="flex items-center gap-2 text-surface/70 hover:text-accent transition-colors mb-8 text-sm"
      >
        <ArrowLeft className="w-4 h-4" /> Back to Admin
      </button>

      <div className="mb-8 border-b border-surface/10 pb-6 flex justify-between items-end">
        <div>
          <span className="font-mono text-accent text-sm tracking-widest uppercase mb-2 block flex items-center gap-2">
            <Database className="w-4 h-4" /> System Telemetry
          </span>
          <h1 className="font-serif text-3xl sm:text-4xl text-surface">
            LLM Usage Logs
          </h1>
        </div>
        <div className="text-right hidden sm:block">
          <p className="text-xs text-surface/50 uppercase tracking-widest mb-1">Total Requests</p>
          <p className="font-mono text-xl text-accent">{logs.length}</p>
        </div>
      </div>
      
      {logs.length === 0 ? (
        <p className="text-surface/70 italic text-center py-10">No LLM logs found yet. Start an interview to generate data.</p>
      ) : (
        <div className="space-y-4">
          {logs.map((log, idx) => (
            <div key={idx} className="bg-surface/5 border border-surface/10 rounded-xl overflow-hidden transition-all hover:border-accent/30">
              {/* Header row (clickable) */}
              <div 
                className="p-4 sm:p-6 flex flex-col md:flex-row gap-4 md:items-center justify-between cursor-pointer hover:bg-surface/10"
                onClick={() => toggleExpand(idx)}
              >
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="px-2 py-1 bg-accent/10 text-accent border border-accent/20 rounded text-xs font-bold uppercase tracking-wider">
                      {log.agent || 'Unknown'}
                    </span>
                    <span className="text-xs font-mono text-surface/50">
                      {new Date(log.timestamp * 1000).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-sm text-surface/80 font-mono truncate max-w-md">Thread: {log.thread_id}</p>
                </div>
                
                <div className="flex items-center gap-6 justify-between md:justify-end w-full md:w-auto">
                  <div className="text-left md:text-right">
                    <p className="text-xs text-surface/50 uppercase tracking-wider mb-1">Model</p>
                    <p className="text-sm text-surface truncate w-32">{log.model}</p>
                  </div>
                  <div className="flex gap-4 text-right bg-background p-2 rounded border border-surface/10">
                    <div>
                      <p className="text-[10px] text-surface/50 uppercase tracking-wider mb-1">Input Tokens</p>
                      <p className="text-sm font-mono text-surface/80">{log.usage?.prompt_tokens || 0}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-surface/50 uppercase tracking-wider mb-1">Output Tokens</p>
                      <p className="text-sm font-mono text-surface/80">{log.usage?.completion_tokens || 0}</p>
                    </div>
                    <div className="border-l border-surface/20 pl-4">
                      <p className="text-[10px] text-surface/50 uppercase tracking-wider mb-1">Total</p>
                      <p className="text-sm font-mono font-bold text-success">{log.usage?.total_tokens || 0}</p>
                    </div>
                  </div>
                  <div className="text-surface/50">
                    {expandedId === idx ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                  </div>
                </div>
              </div>
              
              {/* Expandable Details */}
              {expandedId === idx && (
                <div className="border-t border-surface/10 bg-background/50 p-4 sm:p-6 space-y-6">
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-widest text-surface/70 mb-3 border-b border-surface/10 pb-2">Messages Sent to LLM</h4>
                    <div className="space-y-4">
                      {log.messages?.map((msg, i) => (
                        <div key={i} className={`p-4 rounded-lg text-sm font-mono overflow-x-auto ${msg.role === 'system' ? 'bg-accent/5 border-l-2 border-accent text-surface/90' : 'bg-surface/5 border border-surface/10 text-surface/80'}`}>
                          <span className="font-bold uppercase tracking-widest text-xs opacity-50 block mb-2">{msg.role}</span>
                          <pre className="whitespace-pre-wrap">{msg.content}</pre>
                        </div>
                      ))}
                    </div>
                  </div>
                  
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-widest text-success mb-3 border-b border-surface/10 pb-2">Raw LLM Response</h4>
                    <div className="bg-surface/5 border-l-2 border-success p-4 rounded-lg text-sm font-mono overflow-x-auto text-surface/90">
                      <pre className="whitespace-pre-wrap">{log.response}</pre>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
