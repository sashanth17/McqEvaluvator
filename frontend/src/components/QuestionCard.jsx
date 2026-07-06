import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '../lib/utils';

export default function QuestionCard({ question, number }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const statusColors = {
    Correct: "bg-success/10 text-success border-success/30",
    Partial: "bg-accent/10 text-accent border-accent/30",
    Incorrect: "bg-error/10 text-error border-error/30",
  };

  return (
    <div className="bg-surface/5 border border-surface/10 rounded-xl overflow-hidden transition-all duration-300 hover:border-surface/20">
      {/* Header (Always visible) */}
      <div 
        className="p-4 sm:p-5 flex items-start gap-3 sm:gap-4 cursor-pointer hover:bg-surface/10 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="font-mono text-muted mt-0.5 sm:mt-1 w-5 sm:w-6 text-sm sm:text-base">{number}</div>
        <div className="flex-1 pr-2">
          <p className={cn("text-surface text-sm sm:text-base font-medium transition-all leading-relaxed", !isExpanded && "line-clamp-2")}>
            {question.questionText}
          </p>
        </div>
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <span className={cn("px-2 py-1 rounded text-[10px] sm:text-xs font-mono font-medium border whitespace-nowrap", statusColors[question.status])}>
            {question.status}
          </span>
          <button className="text-muted hover:text-surface transition-colors p-1">
            {isExpanded ? <ChevronUp className="w-4 h-4 sm:w-5 sm:h-5" /> : <ChevronDown className="w-4 h-4 sm:w-5 sm:h-5" />}
          </button>
        </div>
      </div>

      {/* Expanded Content */}
      <div 
        className={cn(
          "grid transition-all duration-300 ease-in-out",
          isExpanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
        )}
      >
        <div className="overflow-hidden">
          <div className="p-4 sm:p-5 pt-0 sm:pl-[52px] pb-5 border-t border-surface/5 mt-2 space-y-5">
            
            <div>
              <h4 className="text-[10px] sm:text-xs uppercase tracking-wider text-muted font-mono mb-2">Your Answer</h4>
              <p className="text-surface/90 text-sm leading-relaxed bg-surface/5 p-3 rounded-lg border border-surface/10">
                {question.userAnswer}
              </p>
            </div>
            
            <div>
              <h4 className="text-[10px] sm:text-xs uppercase tracking-wider text-muted font-mono mb-2">Ideal Answer</h4>
              <p className="text-surface/70 text-sm leading-relaxed pl-3 border-l-2 border-surface/20 py-1">
                {question.idealAnswer}
              </p>
            </div>

            <div className="bg-accent/5 border border-accent/20 rounded-lg p-3 sm:p-4">
              <h4 className="text-[10px] sm:text-xs uppercase tracking-wider text-accent font-mono mb-1.5 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse"></span>
                AI Feedback
              </h4>
              <p className="text-surface/90 text-sm leading-relaxed">
                {question.aiExplanation}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
