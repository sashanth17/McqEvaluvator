import { cn } from '../lib/utils';

export default function ScoreSummary({ score, accuracy, avgResponseTime, questionsAttempted }) {
  // Determine tier color
  let ringColor = "stroke-success";
  if (score < 50) ringColor = "stroke-error";
  else if (score < 80) ringColor = "stroke-accent";

  return (
    <div className="bg-surface/5 border border-surface/10 rounded-3xl p-8 flex flex-col items-center justify-center relative overflow-hidden">
      <div className="absolute top-0 right-0 w-64 h-64 bg-accent/5 rounded-full blur-3xl -mr-20 -mt-20"></div>
      
      <div className="relative w-48 h-48 mb-8">
        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="45" fill="none" className="stroke-surface/10" strokeWidth="6" />
          <circle 
            cx="50" 
            cy="50" 
            r="45" 
            fill="none" 
            className={cn("transition-all duration-1000 ease-out", ringColor)} 
            strokeWidth="6"
            strokeDasharray="283"
            strokeDashoffset={283 - (283 * score) / 100}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute top-0 left-0 w-full h-full flex flex-col items-center justify-center">
          <span className="font-mono text-6xl font-bold text-surface tracking-tighter">{score}</span>
          <span className="font-mono text-muted text-sm mt-1">/ 100</span>
        </div>
      </div>

      <div className="grid grid-cols-3 w-full gap-4 divide-x divide-surface/10 text-center">
        <div className="flex flex-col px-2">
          <span className="text-muted text-[10px] sm:text-xs uppercase tracking-wider mb-1">Accuracy</span>
          <span className="font-mono text-base sm:text-lg text-surface">{accuracy}</span>
        </div>
        <div className="flex flex-col px-2">
          <span className="text-muted text-[10px] sm:text-xs uppercase tracking-wider mb-1">Avg Time</span>
          <span className="font-mono text-base sm:text-lg text-surface">{avgResponseTime}</span>
        </div>
        <div className="flex flex-col px-2">
          <span className="text-muted text-[10px] sm:text-xs uppercase tracking-wider mb-1">Attempted</span>
          <span className="font-mono text-base sm:text-lg text-surface">{questionsAttempted}</span>
        </div>
      </div>
    </div>
  );
}
