import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useInterview } from '../context/InterviewContext';
import InterviewerTile from './InterviewerTile';
import CallControls from './CallControls';
import ResponsePanel from './ResponsePanel';

export default function InterviewScreen() {
  const { questions, currentQuestionIndex, setCurrentQuestionIndex, submitAnswer, isInterviewComplete } = useInterview();
  const navigate = useNavigate();
  
  const [isMicOn, setIsMicOn] = useState(true);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

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

  const currentQuestionText = questions[currentQuestionIndex];
  // Hardcoded total questions for the progress bar since it's dynamic
  const progressPercent = Math.min(((currentQuestionIndex) / 2) * 100, 100);

  const handleAnswerSubmit = async (answerText) => {
    setIsSubmitting(true);
    setIsTransitioning(true); // Show loader while generating next question
    
    await submitAnswer(answerText);
    
    setCurrentQuestionIndex(prev => prev + 1);
    setIsTransitioning(false); // Hide loader and show next question
    setIsSubmitting(false);
  };

  return (
    <div className="flex-1 flex flex-col p-4 sm:p-6 w-full h-full min-h-screen relative pb-10">
      {/* Top Progress Bar */}
      <div className="w-full max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-between mb-4 sm:mb-6 gap-2">
        <span className="font-mono text-sm text-muted">
          Question {currentQuestionIndex + 1} of {questions.length}
        </span>
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
