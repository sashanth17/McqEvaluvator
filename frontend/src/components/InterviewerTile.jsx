import { cn } from '../lib/utils';
import { Loader2 } from 'lucide-react';

export default function InterviewerTile({ questionText, isTransitioning }) {
  return (
    <div className={cn(
      "w-full h-64 sm:h-80 md:h-[400px] bg-surface/5 rounded-2xl border border-surface/10 relative overflow-hidden flex flex-col justify-end p-8 transition-all duration-500",
      isTransitioning ? "opacity-50 scale-95" : "opacity-100 scale-100"
    )}>
      {/* Abstract Animated Avatar (Concentric Rings) */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center justify-center opacity-40">
        <div className="w-40 h-40 rounded-full border border-accent/20 absolute animate-ping" style={{ animationDuration: '3s' }} />
        <div className="w-28 h-28 rounded-full border border-accent/40 absolute animate-ping" style={{ animationDuration: '2.5s', animationDelay: '0.5s' }} />
        <div className="w-16 h-16 rounded-full border border-accent/60 absolute animate-ping" style={{ animationDuration: '2s', animationDelay: '1s' }} />
        <div className="w-8 h-8 rounded-full bg-accent/80 shadow-[0_0_20px_rgba(59,130,246,0.6)]" />
      </div>

      <div className="relative z-10 max-w-3xl flex h-full">
        {isTransitioning ? (
          <div className="w-full h-full flex flex-col items-center justify-center gap-4 text-surface">
             <Loader2 className="w-12 h-12 animate-spin text-accent" />
             <span className="text-lg font-medium opacity-80">Generating Question...</span>
          </div>
        ) : (
          <div className="mt-auto">
            <h2 className="font-serif text-2xl sm:text-3xl md:text-4xl text-surface leading-snug drop-shadow-lg">
              {questionText}
            </h2>
          </div>
        )}
      </div>
    </div>
  );
}
