import { useState, useEffect } from 'react';
import { Mic, Send } from 'lucide-react';
import { cn } from '../lib/utils';

export default function ResponsePanel({ onSubmit, isSubmitting }) {
  const [activeTab, setActiveTab] = useState('type');
  const [textAnswer, setTextAnswer] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [audioStubbed, setAudioStubbed] = useState(false);
  const [glow, setGlow] = useState(false);

  const handleSubmit = () => {
    if (activeTab === 'type' && textAnswer.trim()) {
      onSubmit(textAnswer);
      setTextAnswer(''); // Reset for next question
    } else if (activeTab === 'speak' && audioStubbed) {
      onSubmit("[Audio response submitted]");
      setAudioStubbed(false); // Reset for next question
    }
  };

  const handleMicToggle = () => {
    if (!isRecording) {
      setIsRecording(true);
      setAudioStubbed(false);
      // Stub: Stop recording automatically after 3 seconds
      setTimeout(() => {
        setIsRecording(false);
        setAudioStubbed(true);
      }, 3000);
    } else {
      setIsRecording(false);
      setAudioStubbed(true);
    }
  };

  const canSubmit = (activeTab === 'type' && textAnswer.trim().length > 0) || (activeTab === 'speak' && audioStubbed);

  return (
    <div className="w-full max-w-4xl mx-auto mt-6 flex flex-col items-center">
      <div className="flex bg-surface/10 rounded-full p-1 mb-6">
        <button
          onClick={() => setActiveTab('type')}
          className={cn(
            "px-6 py-2 rounded-full text-sm font-medium transition-all focus:outline-none",
            activeTab === 'type' ? "bg-surface text-background shadow-md" : "text-surface/70 hover:text-surface"
          )}
        >
          Type
        </button>
        <button
          onClick={() => setActiveTab('speak')}
          className={cn(
            "px-6 py-2 rounded-full text-sm font-medium transition-all focus:outline-none",
            activeTab === 'speak' ? "bg-surface text-background shadow-md" : "text-surface/70 hover:text-surface"
          )}
        >
          Speak
        </button>
      </div>

      <div 
        className={cn(
          "w-full bg-surface/5 border rounded-2xl p-6 min-h-[160px] flex flex-col relative transition-all duration-300",
          glow && activeTab === 'type' ? "border-accent shadow-[0_0_15px_rgba(232,165,60,0.15)]" : "border-surface/10"
        )}
      >
        {activeTab === 'type' ? (
          <textarea
            className="w-full flex-1 bg-transparent border-none resize-none text-surface placeholder:text-surface/30 focus:outline-none focus:ring-0 text-lg"
            placeholder="Type your response here..."
            value={textAnswer}
            onChange={(e) => setTextAnswer(e.target.value)}
            disabled={isSubmitting}
            onFocus={() => setGlow(true)}
            onBlur={() => setGlow(false)}
          />
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center">
            <button
              onClick={handleMicToggle}
              disabled={isSubmitting}
              className={cn(
                "w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 shadow-xl focus:outline-none focus:ring-4 focus:ring-accent/50",
                isRecording ? "bg-error text-surface animate-pulse scale-110 shadow-[0_0_30px_rgba(217,112,106,0.5)]" : 
                audioStubbed ? "bg-success text-surface" : "bg-surface/20 text-surface hover:bg-accent hover:text-background"
              )}
            >
              <Mic className="w-8 h-8" />
            </button>
            <p className="text-sm text-muted mt-4">
              {isRecording ? "Recording... (tap to stop)" : audioStubbed ? "Recording complete!" : "Tap to start recording"}
            </p>
          </div>
        )}

        <div className="flex justify-end mt-4">
          <button
            onClick={handleSubmit}
            disabled={!canSubmit || isSubmitting}
            className={cn(
              "flex items-center gap-2 px-6 py-2 rounded-full font-medium transition-all focus:outline-none focus:ring-2 focus:ring-accent",
              canSubmit && !isSubmitting
                ? "bg-accent text-background hover:bg-accent/90 shadow-md transform hover:-translate-y-0.5"
                : "bg-surface/10 text-surface/30 cursor-not-allowed"
            )}
          >
            {isSubmitting ? "Submitting..." : "Submit & Next Question"}
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
