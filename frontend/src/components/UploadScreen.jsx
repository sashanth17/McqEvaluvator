import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Layers } from 'lucide-react';
import FileDropzone from './FileDropzone';
import { useInterview } from '../context/InterviewContext';
import { cn } from '../lib/utils';

export default function UploadScreen() {
  const [error, setError] = useState(null);
  const [classificationOption, setClassificationOption] = useState(1);
  const navigate = useNavigate();
  const { uploadedFile, startInterview } = useInterview();
  const [isStarting, setIsStarting] = useState(false);

  const handleStart = async () => {
    if (uploadedFile) {
      setIsStarting(true);
      try {
          await startInterview();
          navigate('/interview');
      } catch (err) {
          setError(err.message || "Failed to start interview");
          setIsStarting(false);
      }
    }
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 w-full h-full min-h-screen">
      <div className="w-full max-w-[640px] flex flex-col items-center text-center my-8">
        <span className="font-mono text-accent text-sm tracking-widest uppercase mb-3">
          Step 01 — Upload & Classification
        </span>
        <h1 className="font-serif text-4xl sm:text-5xl text-surface mb-3">
          Drop in your question set.
        </h1>
        <p className="text-muted mb-8 text-lg max-w-[500px]">
          Choose how you want your questions analyzed, then upload your CSV file.
        </p>

        {/* Classification Option Selector */}
        <div className="w-full max-w-[520px] grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8 text-left">
          {/* Option 1 Card */}
          <div
            onClick={() => setClassificationOption(1)}
            className={cn(
              "p-4 rounded-xl border-2 cursor-pointer transition-all duration-200 flex flex-col justify-between relative",
              classificationOption === 1
                ? "border-accent bg-accent/10 shadow-md"
                : "border-surface/20 bg-surface/5 hover:border-surface/40 hover:bg-surface/10"
            )}
          >
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className={cn("w-5 h-5", classificationOption === 1 ? "text-accent" : "text-muted")} />
              <span className="font-medium text-surface text-base">Option 1</span>
            </div>
            <h4 className="font-semibold text-surface text-sm mb-1">
              Auto Topic & Concept Classification
            </h4>
            <p className="text-muted text-xs leading-relaxed">
              LLM automatically clusters questions into macro-topics and extracts tested concepts.
            </p>
          </div>

          {/* Option 2 Card */}
          <div
            onClick={() => setClassificationOption(2)}
            className={cn(
              "p-4 rounded-xl border-2 cursor-pointer transition-all duration-200 flex flex-col justify-between relative",
              classificationOption === 2
                ? "border-accent bg-accent/10 shadow-md"
                : "border-surface/20 bg-surface/5 hover:border-surface/40 hover:bg-surface/10"
            )}
          >
            <div className="flex items-center gap-2 mb-2">
              <Layers className={cn("w-5 h-5", classificationOption === 2 ? "text-accent" : "text-muted")} />
              <span className="font-medium text-surface text-base">Option 2</span>
            </div>
            <h4 className="font-semibold text-surface text-sm mb-1">
              Pre-defined CSV Topic Column
            </h4>
            <p className="text-muted text-xs leading-relaxed">
              CSV already has a <code className="bg-surface/10 px-1 py-0.5 rounded text-accent">Topic</code> column. LLM extracts concepts & organizes by topic.
            </p>
          </div>
        </div>

        <FileDropzone 
          classificationOption={classificationOption}
          onUploadSuccess={() => setError(null)} 
          onError={(msg) => setError(msg)} 
        />

        {error && (
          <p className="text-error mt-4 text-sm font-medium">
            {error}
          </p>
        )}

        <button
          onClick={handleStart}
          disabled={!uploadedFile || isStarting}
          className={cn(
            "mt-8 px-8 py-3 rounded-full font-medium transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-background",
            uploadedFile && !isStarting
              ? "bg-accent text-background hover:bg-accent/90 cursor-pointer" 
              : "bg-surface/20 text-surface/40 cursor-not-allowed opacity-40"
          )}
        >
          {isStarting ? "Starting..." : "Start Interview"}
        </button>
      </div>
    </div>
  );
}
