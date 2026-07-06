import React, { createContext, useContext, useState } from 'react';

const InterviewContext = createContext();

export function useInterview() {
  return useContext(InterviewContext);
}

export function InterviewProvider({ children }) {
  const [uploadedFile, setUploadedFile] = useState(null);
  const [threadId, setThreadId] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [isInterviewComplete, setIsInterviewComplete] = useState(false);
  const [reportData, setReportData] = useState(null);

  // API: uploadFile
  const uploadFile = async (file) => {
    if (file.size > 10 * 1024 * 1024) {
      throw new Error("File too large. Max 10MB allowed.");
    }
    
    const formData = new FormData();
    formData.append("file", file);

    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    
    const response = await fetch(`${apiUrl}/upload`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || "Upload failed");
    }

    const data = await response.json();
    
    setUploadedFile({
      name: file.name,
      size: file.size,
      url: data.url,
      context_id: data.context_id
    });
  };

  // API: startInterview
  const startInterview = async () => {
    if (!uploadedFile?.context_id) return;
    
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const response = await fetch(`${apiUrl}/start_interview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ context_id: uploadedFile.context_id })
    });
    
    if (!response.ok) throw new Error("Failed to start interview");
    
    const data = await response.json();
    setThreadId(data.thread_id);
    
    const qText = data.generated_question?.question || "Can you explain this topic?";
    setQuestions([qText]);
    setCurrentQuestionIndex(0);
  };

  // API: submitAnswer
  const submitAnswer = async (answerText) => {
    setAnswers((prev) => [...prev, { questionId: currentQuestionIndex, answer: answerText }]);
    
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const response = await fetch(`${apiUrl}/submit_answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thread_id: threadId, student_answer: answerText })
    });
    
    const data = await response.json();
    
    if (data.is_complete) {
        setIsInterviewComplete(true);
        setReportData(data.report);
    } else {
        const nextQText = data.generated_question?.question || "No question received";
        setQuestions((prev) => [...prev, nextQText]);
    }
  };

  // API: fetchReport
  const fetchReport = async () => {
    return reportData;
  };

  const resetInterview = () => {
    setUploadedFile(null);
    setThreadId(null);
    setQuestions([]);
    setAnswers([]);
    setCurrentQuestionIndex(0);
    setIsInterviewComplete(false);
    setReportData(null);
  };

  const value = {
    uploadedFile,
    threadId,
    questions,
    answers,
    currentQuestionIndex,
    setCurrentQuestionIndex,
    isInterviewComplete,
    uploadFile,
    startInterview,
    submitAnswer,
    fetchReport,
    resetInterview
  };

  return (
    <InterviewContext.Provider value={value}>
      {children}
    </InterviewContext.Provider>
  );
}
