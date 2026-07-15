import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useInterview } from '../context/InterviewContext';
import InterviewerTile from './InterviewerTile';
import CallControls from './CallControls';
import ResponsePanel from './ResponsePanel';

export default function InterviewScreen() {
  const { questions, currentQuestionIndex, setCurrentQuestionIndex, submitAnswer, stopInterview, isInterviewComplete } = useInterview();
  const navigate = useNavigate();
  
  const [isMicOn, setIsMicOn] = useState(true);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  
  const startTimeRef = useRef(Date.now());

  useEffect(() => {
    // If no questions loaded, redirect back to upload
    if (!questions || questions.length === 0) {
      navigate('/upload');
    }
  }, [questions, navigate]);

  useEffect(() => {
    if (isInterviewComplete) {
      navigate('/report');
    }
  }, [isInterviewComplete, navigate]);

  if (!questions || questions.length === 0) return null;

  const currentQuestionData = questions[currentQuestionIndex] || {};
  const currentQuestionText = typeof currentQuestionData === 'string' ? currentQuestionData : currentQuestionData.text;
  const audioUrl = currentQuestionData.audioUrl;
  
  const audioRef = useRef(null);

  useEffect(() => {
    // Reset timer when question changes
    startTimeRef.current = Date.now();
    
    if (audioUrl) {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const audio = new Audio(apiUrl + audioUrl);
      audioRef.current = audio;
      
      audio.onended = () => setIsPlaying(false);
      audio.onplay = () => setIsPlaying(true);
      audio.onpause = () => setIsPlaying(false);
      
      audio.play().catch(e => console.error("Auto-play failed:", e));
    }
  }, [audioUrl, currentQuestionIndex]);

  const toggleAudio = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play().catch(e => console.error("Play failed:", e));
      }
    }
  };

  const replayAudio = () => {
    if (audioRef.current) {
      audioRef.current.currentTime = 0;
      audioRef.current.play().catch(e => console.error("Replay failed:", e));
    }
  };

  // Hardcoded total questions for the progress bar since it's dynamic
  const progressPercent = Math.min(((currentQuestionIndex) / 2) * 100, 100);

  const handleAnswerSubmit = async (answerText) => {
    setIsSubmitting(true);
    setIsTransitioning(true); // Show loader while generating next question
    
    if (audioRef.current) {
      audioRef.current.pause();
    }
    
    const timeTakenSeconds = Math.round((Date.now() - startTimeRef.current) / 1000);
    
    await submitAnswer(answerText, timeTakenSeconds);
    
    setCurrentQuestionIndex(prev => prev + 1);
    setIsTransitioning(false); // Hide loader and show next question
    setIsSubmitting(false);
  };

  return (
    <div className="flex-1 flex flex-col p-4 sm:p-6 w-full h-full min-h-screen relative pb-10">
      {/* Top Progress Bar */}
      <div className="w-full max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-between mb-4 sm:mb-6 gap-2">
        <div className="flex items-center gap-4">
          <span className="font-mono text-sm text-muted">
            Question {currentQuestionIndex + 1} of {questions.length}
          </span>
          <button 
            onClick={stopInterview}
            className="px-3 py-1 bg-red-500/20 text-red-500 hover:bg-red-500/30 rounded-full text-xs font-medium transition-colors"
          >
            End & View Report
          </button>
        </div>
        <div className="w-full sm:w-64 h-1 bg-surface/10 rounded-full overflow-hidden">
          <div 
            className="h-full bg-accent transition-all duration-500 ease-in-out" 
            style={{ width: `${progressPercent}%` }} 
          />
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 w-full max-w-4xl mx-auto flex flex-col relative pb-6">
        <InterviewerTile 
          questionText={currentQuestionText} 
          isTransitioning={isTransitioning} 
          isPlaying={isPlaying}
          onTogglePlay={toggleAudio}
          onReplay={replayAudio}
        />
        
        <CallControls 
          isMicOn={isMicOn}
          setIsMicOn={setIsMicOn}
        />
        
        <ResponsePanel 
          onSubmit={handleAnswerSubmit} 
          isSubmitting={isSubmitting} 
        />
      </div>
    </div>
  );
}
