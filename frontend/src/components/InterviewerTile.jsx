import { cn } from '../lib/utils';
import { Loader2, Play, Pause, RotateCcw } from 'lucide-react';

export default function InterviewerTile({ questionText, isTransitioning, isPlaying, onTogglePlay, onReplay }) {
  return (
    <div className={cn(
      "w-full h-64 sm:h-80 md:h-[400px] bg-surface/5 rounded-2xl border border-surface/10 relative overflow-hidden flex flex-col justify-end p-8 transition-all duration-500",
      isTransitioning ? "opacity-50 scale-95" : "opacity-100 scale-100"
    )}>
      {/* Abstract Animated Avatar (Concentric Rings) */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center justify-center opacity-40">
        <div className={cn("w-40 h-40 rounded-full border border-accent/20 absolute", isPlaying && "animate-ping")} style={{ animationDuration: '3s' }} />
        <div className={cn("w-28 h-28 rounded-full border border-accent/40 absolute", isPlaying && "animate-ping")} style={{ animationDuration: '2.5s', animationDelay: '0.5s' }} />
        <div className={cn("w-16 h-16 rounded-full border border-accent/60 absolute", isPlaying && "animate-ping")} style={{ animationDuration: '2s', animationDelay: '1s' }} />
        <div className={cn("w-8 h-8 rounded-full bg-accent/80 shadow-[0_0_20px_rgba(59,130,246,0.6)]", isPlaying && "shadow-[0_0_30px_rgba(59,130,246,0.9)]")} />
      </div>

      {/* Audio Controls Overlay */}
      {!isTransitioning && (
        <div className="absolute top-4 right-4 z-20 flex items-center gap-2 bg-background/50 backdrop-blur-sm p-1.5 rounded-full border border-surface/10">
          <button 
            onClick={onTogglePlay}
            className="p-2 rounded-full hover:bg-surface/10 text-surface/80 hover:text-accent transition-colors"
            title={isPlaying ? "Pause Audio" : "Play Audio"}
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
          </button>
          <div className="w-px h-4 bg-surface/20"></div>
          <button 
            onClick={onReplay}
            className="p-2 rounded-full hover:bg-surface/10 text-surface/80 hover:text-accent transition-colors"
            title="Replay Audio"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
      )}

      <div className="relative z-10 max-w-3xl flex h-full">
        {isTransitioning ? (
          <div className="w-full h-full flex flex-col items-center justify-center gap-4 text-surface">
             <Loader2 className="w-12 h-12 animate-spin text-accent" />
             <span className="text-lg font-medium opacity-80">Generating Question...</span>
          </div>
        ) : (
          <div className="mt-auto w-full max-h-full overflow-y-auto pr-2 custom-scrollbar">
            <h2 className="font-serif text-2xl sm:text-3xl md:text-4xl text-surface leading-snug drop-shadow-lg">
              {questionText}
            </h2>
          </div>
        )}
      </div>
    </div>
  );
}
