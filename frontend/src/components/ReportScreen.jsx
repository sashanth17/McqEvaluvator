import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useInterview } from '../context/InterviewContext';
import { Download, RefreshCw, CheckCircle2, AlertTriangle, Target } from 'lucide-react';
import { cn } from '../lib/utils';

export default function ReportScreen({ propReport }) {
  const { fetchReport, resetInterview } = useInterview();
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadReport() {
      try {
        if (propReport) {
          setReport(propReport);
          return;
        }
        
        const data = await fetchReport();
        if (data) {
           setReport(data);
        } else {
           navigate('/upload');
        }
      } catch (err) {
        console.error("Failed to load report", err);
      } finally {
        setLoading(false);
      }
    }
    loadReport();
  }, [fetchReport, navigate, propReport]);

  const handleRetake = () => {
    resetInterview();
    navigate('/upload');
  };

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center h-full min-h-screen">
        <div className="w-12 h-12 border-4 border-accent border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-surface font-mono animate-pulse">Synthesizing your assessment report...</p>
      </div>
    );
  }

  if (!report) return null;

  if (!report.assessment_summary) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center h-full min-h-screen p-6">
        <h2 className="text-xl text-error mb-4">Report format invalid or unavailable</h2>
        <pre className="bg-surface/10 p-4 rounded-xl text-surface/70 text-sm overflow-auto max-w-2xl w-full">
           {JSON.stringify(report, null, 2)}
        </pre>
        <button onClick={handleRetake} className="mt-8 px-8 py-3 bg-accent text-background rounded-full">Return Home</button>
      </div>
    );
  }

  const { session_metrics, assessment_summary, topic_analysis, reasoning_profile, key_strengths, priority_improvement_areas, final_summary } = report;

  const getUnderstandingColor = (level) => {
    switch(level) {
      case 'strong': return 'text-success border-success/30 bg-success/10';
      case 'moderate': return 'text-accent border-accent/30 bg-accent/10';
      case 'weak': return 'text-error border-error/30 bg-error/10';
      default: return 'text-muted border-muted/30 bg-muted/10';
    }
  };

  return (
    <div className="flex-1 w-full max-w-6xl mx-auto p-4 sm:p-6 lg:p-8 pb-20">
      <div className="mb-8">
        <span className="font-mono text-accent text-sm tracking-widest uppercase mb-2 block">
          Step 03 — Final Assessment
        </span>
        <h1 className="font-serif text-3xl sm:text-4xl md:text-5xl text-surface">
          Interview Report
        </h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12">
        {/* Left Column: Summary */}
        <div className="lg:col-span-5 flex flex-col gap-6">
          {session_metrics && (
            <div className="bg-surface/5 border border-surface/10 rounded-2xl p-6">
              <h3 className="font-serif text-xl mb-4 border-b border-surface/10 pb-2">MCQ Summary</h3>
              
              <div className="flex flex-col gap-4">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-surface/80">Total Questions Correct</span>
                  <p className="text-3xl font-mono">
                    <span className="text-success font-bold">{session_metrics.total_answered_correctly}</span>
                    <span className="text-surface/30 mx-2">/</span>
                    <span className="text-surface/60 text-xl">{session_metrics.total_questions_asked}</span>
                  </p>
                </div>
                
                {session_metrics.total_topics && (
                  <div className="flex justify-between items-center border-t border-surface/5 pt-3">
                    <span className="text-sm text-surface/80">Total Topics Evaluated</span>
                    <p className="text-xl font-mono text-accent font-medium">
                      {session_metrics.total_topics}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="bg-surface/5 border border-surface/10 rounded-2xl p-6">
            <h3 className="font-serif text-xl mb-4 border-b border-surface/10 pb-2">Overall Understanding</h3>
            <div className="mb-4">
              <span className={cn("px-4 py-1.5 rounded-full text-sm font-semibold uppercase tracking-wider border", getUnderstandingColor(assessment_summary.overall_understanding))}>
                {assessment_summary.overall_understanding.replace('_', ' ')}
              </span>
            </div>
            <p className="text-surface/80 text-sm leading-relaxed">{assessment_summary.summary}</p>
          </div>

          {assessment_summary.communication_skills && (
            <div className="bg-surface/5 border border-surface/10 rounded-2xl p-6">
              <h3 className="font-serif text-xl mb-4 border-b border-surface/10 pb-2">Communication Skills</h3>
              <div className="space-y-4">
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-widest text-accent mb-1">Articulation</h4>
                  <p className="text-surface/80 text-sm leading-relaxed">{assessment_summary.communication_skills.articulation}</p>
                </div>
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-widest text-success mb-1">Confidence</h4>
                  <p className="text-surface/80 text-sm leading-relaxed">{assessment_summary.communication_skills.confidence}</p>
                </div>
              </div>
            </div>
          )}

          <div className="bg-surface/5 border border-surface/10 rounded-2xl p-6">
             <h3 className="font-serif text-xl mb-4 border-b border-surface/10 pb-2">Reasoning Profile</h3>
             <div className="mb-4">
               <span className="px-4 py-1.5 rounded-full text-sm font-semibold uppercase tracking-wider border text-accent border-accent/30 bg-accent/10">
                 Depth: {reasoning_profile.reasoning_depth}
               </span>
             </div>
             <p className="text-surface/80 text-sm leading-relaxed">{reasoning_profile.summary}</p>
          </div>

          <div className="bg-surface/5 border border-surface/10 rounded-2xl p-6">
             <h3 className="font-serif text-xl mb-4 border-b border-surface/10 pb-2 flex items-center gap-2">
               <CheckCircle2 className="w-5 h-5 text-success" /> Key Strengths
             </h3>
             <ul className="space-y-3">
               {key_strengths.map((s, i) => (
                 <li key={i} className="text-sm text-surface/80 flex items-start gap-2">
                   <div className="w-1.5 h-1.5 rounded-full bg-success mt-1.5 shrink-0" />
                   {s}
                 </li>
               ))}
             </ul>
          </div>

          <div className="bg-surface/5 border border-surface/10 rounded-2xl p-6">
             <h3 className="font-serif text-xl mb-4 border-b border-surface/10 pb-2 flex items-center gap-2">
               <AlertTriangle className="w-5 h-5 text-error" /> Priority Improvements
             </h3>
             <ul className="space-y-3">
               {priority_improvement_areas.map((p, i) => (
                 <li key={i} className="text-sm text-surface/80 flex items-start gap-2">
                   <div className="w-1.5 h-1.5 rounded-full bg-error mt-1.5 shrink-0" />
                   {p}
                 </li>
               ))}
             </ul>
          </div>
        </div>

        {/* Right Column: Topic Breakdown */}
        <div className="lg:col-span-7 flex flex-col h-full">
          <div className="bg-surface/5 border border-surface/10 rounded-2xl p-6 mb-6">
             <h3 className="font-serif text-xl mb-3 flex items-center gap-2">
               <Target className="w-5 h-5 text-accent" /> Final Conclusion
             </h3>
             <p className="text-surface/90 italic font-serif text-lg leading-relaxed">
               "{final_summary}"
             </p>
          </div>

          <h3 className="font-serif text-2xl text-surface mb-6 border-b border-surface/10 pb-2">
            Topic Analysis
          </h3>
          
          <div className="space-y-6 lg:max-h-[60vh] lg:overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-surface/20 scrollbar-track-transparent">
            {topic_analysis.map((topic, idx) => (
              <div key={idx} className="bg-surface/5 border border-surface/10 rounded-2xl p-6 relative overflow-hidden group hover:border-surface/20 transition-colors">
                <div className="absolute top-0 left-0 w-1 h-full bg-accent opacity-50 group-hover:opacity-100 transition-opacity" />
                <h4 className="text-xl font-medium mb-3">{topic.topic}</h4>
                <div className="flex flex-wrap gap-2 mb-4">
                  <span className={cn("px-3 py-1 rounded-md text-xs font-semibold uppercase tracking-wider border", getUnderstandingColor(topic.understanding_level))}>
                    Level: {topic.understanding_level.replace('_', ' ')}
                  </span>
                  <span className="px-3 py-1 rounded-md text-xs font-semibold uppercase tracking-wider border text-surface/60 border-surface/20 bg-surface/10">
                    Depth: {topic.depth}
                  </span>
                  <span className="px-3 py-1 rounded-md text-xs font-semibold uppercase tracking-wider border text-surface/60 border-surface/20 bg-surface/10">
                    Consistency: {topic.mcq_interview_consistency.replace(/_/g, ' ')}
                  </span>
                  {topic.average_time_taken_seconds && (
                    <span className="px-3 py-1 rounded-md text-xs font-semibold uppercase tracking-wider border text-accent/70 border-accent/20 bg-accent/5">
                      Avg Time: {topic.average_time_taken_seconds}s
                    </span>
                  )}
                  {topic.mcq_questions_asked !== undefined && (
                    <span className="px-3 py-1 rounded-md text-xs font-semibold uppercase tracking-wider border text-success/70 border-success/20 bg-success/5">
                      MCQ: {topic.mcq_questions_correct} / {topic.mcq_questions_asked} Correct
                    </span>
                  )}
                </div>
                <p className="text-sm text-surface/80 mb-6">{topic.feedback}</p>
                
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                   {topic.knowledge_gaps.length > 0 && (
                     <div>
                       <h5 className="text-sm font-semibold text-error mb-2">Knowledge Gaps</h5>
                       <ul className="space-y-2">
                         {topic.knowledge_gaps.map((g, i) => (
                           <li key={i} className="text-xs text-surface/70 flex items-start gap-1.5">
                             <span className="text-error mt-0.5">•</span> {g}
                           </li>
                         ))}
                       </ul>
                     </div>
                   )}
                   {topic.misconceptions.length > 0 && (
                     <div>
                       <h5 className="text-sm font-semibold text-accent mb-2">Misconceptions</h5>
                       <ul className="space-y-2">
                         {topic.misconceptions.map((m, i) => (
                           <li key={i} className="text-xs text-surface/70 flex items-start gap-1.5">
                             <span className="text-accent mt-0.5">•</span> {m}
                           </li>
                         ))}
                       </ul>
                     </div>
                   )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer Actions */}
      <div className="mt-12 flex flex-col sm:flex-row items-center gap-4 border-t border-surface/10 pt-8">
        <button 
          onClick={handleRetake}
          className="w-full sm:w-auto flex items-center justify-center gap-2 px-8 py-3 rounded-full font-medium bg-accent text-background hover:bg-accent/90 transition-all focus:outline-none focus:ring-2 focus:ring-accent"
        >
          <RefreshCw className="w-5 h-5" />
          Start New Interview
        </button>
        <button 
          className="w-full sm:w-auto flex items-center justify-center gap-2 px-8 py-3 rounded-full font-medium bg-transparent border border-surface/20 text-surface hover:bg-surface/10 transition-all focus:outline-none focus:ring-2 focus:ring-surface/30"
          onClick={() => alert("Downloading PDF report (Stub)")}
        >
          <Download className="w-5 h-5" />
          Download Full Report
        </button>
      </div>
    </div>
  );
}
