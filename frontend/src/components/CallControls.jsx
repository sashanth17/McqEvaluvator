import { Mic, MicOff } from 'lucide-react';
import { cn } from '../lib/utils';
import { useState, useEffect } from 'react';

export default function CallControls({ isMicOn, setIsMicOn }) {
  const [elapsedTime, setElapsedTime] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setElapsedTime(prev => prev + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  return (
    <div className="flex items-center justify-between w-full max-w-xl px-6 py-4 bg-surface/5 backdrop-blur-md rounded-2xl border border-surface/10 mx-auto mt-6">
      <div className="flex items-center gap-3 w-20">
        <div className="w-2.5 h-2.5 bg-error rounded-full animate-pulse" />
        <span className="font-mono text-sm tracking-wider">LIVE</span>
      </div>

      <div className="flex gap-4 flex-1 justify-center">
        <button 
          onClick={() => setIsMicOn(!isMicOn)}
          className={cn(
            "p-4 rounded-full transition-all focus:outline-none focus:ring-2 focus:ring-accent",
            isMicOn ? "bg-surface/20 text-surface hover:bg-surface/30" : "bg-error/20 text-error hover:bg-error/30"
          )}
        >
          {isMicOn ? <Mic className="w-5 h-5" /> : <MicOff className="w-5 h-5" />}
        </button>
      </div>

      <div className="font-mono text-sm tracking-wider text-muted w-20 text-right">
        {formatTime(elapsedTime)}
      </div>
    </div>
  );
}
