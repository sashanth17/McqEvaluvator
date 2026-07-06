import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import FileDropzone from './FileDropzone';
import { useInterview } from '../context/InterviewContext';
import { cn } from '../lib/utils';

export default function UploadScreen() {
  const [error, setError] = useState(null);
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
      <div className="w-full max-w-[560px] flex flex-col items-center text-center -mt-16">
        <span className="font-mono text-accent text-sm tracking-widest uppercase mb-4">
          Step 01 — Upload
        </span>
        <h1 className="font-serif text-4xl sm:text-5xl text-surface mb-4">
          Drop in your question set.
        </h1>
        <p className="text-muted mb-10 text-lg">
          Upload a PDF, DOCX, or CSV of your questions. We'll prep them for your interview.
        </p>

        <FileDropzone 
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
          disabled={!uploadedFile}
          className={cn(
            "mt-10 px-8 py-3 rounded-full font-medium transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-background",
            uploadedFile 
              ? "bg-accent text-background hover:bg-accent/90 cursor-pointer" 
              : "bg-surface/20 text-surface/40 cursor-not-allowed opacity-40"
          )}
        >
          Start Interview
        </button>
      </div>
    </div>
  );
}
