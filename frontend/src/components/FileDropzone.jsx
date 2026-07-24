import { useState, useRef } from 'react';
import { UploadCloud, CheckCircle2, FileText } from 'lucide-react';
import { cn } from '../lib/utils';
import { useInterview } from '../context/InterviewContext';

export default function FileDropzone({ classificationOption = 1, onUploadSuccess, onError }) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const fileInputRef = useRef(null);
  const { uploadFile, uploadedFile } = useInterview();

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const processFile = async (file) => {
    if (!file) return;
    setIsUploading(true);
    onError(null);
    setProgress(0);

    // Simulate progress animation
    const progressInterval = setInterval(() => {
      setProgress(p => Math.min(p + 10, 90));
    }, 150);

    try {
      await uploadFile(file, classificationOption);
      setProgress(100);
      setTimeout(() => {
        setIsUploading(false);
        if (onUploadSuccess) onUploadSuccess();
      }, 500);
    } catch (err) {
      setIsUploading(false);
      onError(err.message);
    } finally {
      clearInterval(progressInterval);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      processFile(files[0]);
    }
  };

  const handleChange = (e) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      processFile(files[0]);
    }
  };

  // Success State
  if (uploadedFile && !isUploading) {
    return (
      <div className="w-full max-w-[480px] h-[80px] bg-surface/5 border border-surface/20 rounded-xl flex items-center justify-between px-6 transition-all">
        <div className="flex items-center gap-4">
          <FileText className="text-accent w-6 h-6" />
          <div className="flex flex-col text-left">
            <span className="text-surface font-medium truncate max-w-[200px]">{uploadedFile.name}</span>
            <span className="text-muted text-sm font-mono">{(uploadedFile.size / 1024 / 1024).toFixed(2)} MB</span>
          </div>
        </div>
        <div className="flex items-center gap-2 text-success font-medium">
          <CheckCircle2 className="w-5 h-5" />
          <span>Ready to begin.</span>
        </div>
      </div>
    );
  }

  // Uploading State
  if (isUploading) {
    return (
      <div className="w-full max-w-[480px] h-[280px] border-2 border-surface/20 rounded-xl flex flex-col items-center justify-center transition-all bg-surface/5">
        <UploadCloud className="w-10 h-10 text-accent mb-4 animate-bounce" />
        <p className="text-surface font-medium mb-4">Uploading your file...</p>
        <div className="w-64 h-2 bg-surface/20 rounded-full overflow-hidden">
          <div 
            className="h-full bg-accent transition-all duration-300 ease-out" 
            style={{ width: `${progress}%` }} 
          />
        </div>
      </div>
    );
  }

  // Default Dropzone
  return (
    <div
      className={cn(
        "w-full max-w-[480px] h-[280px] border-2 border-dashed rounded-xl flex flex-col items-center justify-center cursor-pointer transition-all duration-300",
        isDragging ? "border-accent bg-accent/5 scale-[1.02]" : "border-surface/30 hover:border-surface hover:bg-surface/5"
      )}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={() => fileInputRef.current?.click()}
    >
      <input
        type="file"
        className="hidden"
        ref={fileInputRef}
        onChange={handleChange}
        accept=".pdf,.docx,.csv"
      />
      <div className="p-4 bg-surface/10 rounded-full mb-4">
        <UploadCloud className="w-8 h-8 text-surface" />
      </div>
      <p className="text-surface font-medium mb-1">Drag and drop your file, or click to browse</p>
      <p className="text-muted text-sm">PDF, DOCX, CSV — up to 10MB</p>
    </div>
  );
}
