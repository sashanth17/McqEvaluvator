import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ReportScreen from './ReportScreen';
import { ArrowLeft } from 'lucide-react';

export default function AdminInterviewDetail() {
  const { threadId } = useParams();
  const navigate = useNavigate();
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchDetail() {
      try {
        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        const res = await fetch(`${apiUrl}/admin/interviews/${threadId}`);
        if (!res.ok) throw new Error("Failed to fetch detail");
        const data = await res.json();
        setDetail(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    fetchDetail();
  }, [threadId]);

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center h-full min-h-screen">
        <div className="w-12 h-12 border-4 border-accent border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-surface font-mono animate-pulse">Loading Interview Data...</p>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="p-8 text-center text-error">
        <p>Failed to load detail for thread {threadId}</p>
        <button onClick={() => navigate('/admin/interviews')} className="mt-4 px-4 py-2 border rounded-full text-surface border-surface/20">Back to Admin</button>
      </div>
    );
  }

  return (
    <div className="flex-1 w-full max-w-6xl mx-auto p-4 sm:p-6 lg:p-8 pb-20">
      <button 
        onClick={() => navigate('/admin/interviews')} 
        className="flex items-center gap-2 text-surface/70 hover:text-accent transition-colors mb-8 text-sm"
      >
        <ArrowLeft className="w-4 h-4" /> Back to Interviews
      </button>

      <div className="mb-12">
        <span className="font-mono text-accent text-sm tracking-widest uppercase mb-2 block">
          Interaction Timeline
        </span>
        <h1 className="font-serif text-3xl sm:text-4xl text-surface border-b border-surface/10 pb-6">
          Detailed Evidence Trail
        </h1>
      </div>

      <div className="space-y-12 mb-16 relative">
        <div className="absolute left-6 top-4 bottom-4 w-px bg-surface/10 hidden md:block"></div>
        {detail.interactions.map((interaction, idx) => (
          <div key={idx} className="relative z-10 grid grid-cols-1 md:grid-cols-12 gap-6 md:gap-12">
             <div className="md:col-span-1 flex justify-center hidden md:flex">
               <div className="w-12 h-12 rounded-full bg-background border border-surface/20 flex items-center justify-center font-mono text-accent text-lg">
                 {idx + 1}
               </div>
             </div>
             <div className="md:col-span-11 space-y-6">
                <div className="bg-surface/5 border border-surface/10 rounded-2xl p-6">
                  <h4 className="text-sm font-semibold text-accent uppercase tracking-wider mb-3">AI Question</h4>
                  <p className="text-surface/90 text-lg font-serif italic mb-4">
                    "{interaction.question?.question}"
                  </p>
                  
                  <div className="bg-surface/10 rounded-xl p-4 border border-surface/10">
                     <h4 className="text-sm font-semibold text-surface/70 uppercase tracking-wider mb-2">Internal Prompt State (state_given_to_questioning_agent)</h4>
                     <pre className="text-xs text-surface/60 overflow-x-auto font-mono max-h-64 scrollbar-thin scrollbar-thumb-surface/20">
                       {JSON.stringify(interaction.state_given_to_questioning_agent, null, 2)}
                     </pre>
                  </div>
                </div>
                
                <div className="bg-surface/10 border-l-4 border-l-accent rounded-r-2xl p-6">
                  <h4 className="text-sm font-semibold text-surface/70 uppercase tracking-wider mb-3">Student Answer</h4>
                  <p className="text-surface/90 text-lg leading-relaxed font-medium">
                    {interaction.student_answer}
                  </p>
                </div>
                
                <div className="bg-surface/5 border border-surface/10 rounded-2xl p-6 border-t-4 border-t-success/50">
                  <h4 className="text-sm font-semibold text-success uppercase tracking-wider mb-3 flex items-center justify-between">
                    Evaluator Assessment
                    <span className="text-xs text-surface/50 normal-case bg-background px-2 py-1 rounded border border-surface/10">Conf: {interaction.evaluation?.assessment_confidence}</span>
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
                     <div className="bg-background border border-surface/10 rounded-lg p-3">
                       <p className="text-xs text-surface/60 uppercase">Understanding</p>
                       <p className="font-semibold text-surface">{interaction.evaluation?.overall_understanding}</p>
                     </div>
                     <div className="bg-background border border-surface/10 rounded-lg p-3">
                       <p className="text-xs text-surface/60 uppercase">Reasoning Depth</p>
                       <p className="font-semibold text-surface">{interaction.evaluation?.reasoning_analysis?.depth}</p>
                     </div>
                     <div className="bg-background border border-surface/10 rounded-lg p-3">
                       <p className="text-xs text-surface/60 uppercase">Continue Topic?</p>
                       <p className="font-semibold text-surface">{interaction.evaluation?.continue_topic ? 'Yes' : 'No'}</p>
                     </div>
                  </div>
                  
                  {interaction.evaluation?.concept_assessment && (
                    <div className="mb-4 bg-background p-4 rounded-xl border border-surface/10">
                       <h5 className="text-xs font-semibold text-surface/70 uppercase mb-2">Concept Assessment</h5>
                       <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                         {interaction.evaluation.concept_assessment.mastered?.length > 0 && (
                           <div>
                             <p className="text-xs text-success mb-1 font-semibold">Mastered</p>
                             <ul className="list-disc pl-4 text-xs text-surface/80">
                               {interaction.evaluation.concept_assessment.mastered.map((c, i) => <li key={i}>{c}</li>)}
                             </ul>
                           </div>
                         )}
                         {interaction.evaluation.concept_assessment.misconceptions?.length > 0 && (
                           <div>
                             <p className="text-xs text-error mb-1 font-semibold">Misconceptions</p>
                             <ul className="list-disc pl-4 text-xs text-surface/80">
                               {interaction.evaluation.concept_assessment.misconceptions.map((c, i) => <li key={i}>{c}</li>)}
                             </ul>
                           </div>
                         )}
                       </div>
                    </div>
                  )}

                  {interaction.evaluation?.evidence_ledger?.length > 0 && (
                    <div className="mb-4 bg-background p-4 rounded-xl border border-surface/10">
                       <h5 className="text-xs font-semibold text-surface/70 uppercase mb-2">Evidence Ledger</h5>
                       <div className="space-y-4">
                         {interaction.evaluation.evidence_ledger.map((ev, i) => (
                           <div key={i} className="text-xs border-l-2 border-accent pl-3">
                             <p className="font-semibold text-surface/90 text-sm mb-1">{ev.claim}</p>
                             <span className="text-accent/80 italic mb-2 inline-block">Strength: {ev.evidence_strength}</span>
                             <ul className="list-disc pl-4 text-surface/70 space-y-1">
                               {ev.supporting_observations?.map((obs, j) => <li key={j}>{obs}</li>)}
                             </ul>
                           </div>
                         ))}
                       </div>
                    </div>
                  )}

                  <p className="text-sm text-surface/80 bg-background p-4 rounded-xl border border-surface/10">
                    <span className="font-semibold block mb-1 text-surface">Feedback Summary:</span>
                    {interaction.evaluation?.feedback_summary}
                  </p>
                </div>
             </div>
          </div>
        ))}
      </div>

      {detail.report && (
        <div className="border-t-[4px] border-surface/20 pt-16 mt-16 rounded-t-[3rem] bg-gradient-to-b from-surface/5 to-transparent -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8">
          <ReportScreen propReport={detail.report} />
        </div>
      )}
    </div>
  );
}
