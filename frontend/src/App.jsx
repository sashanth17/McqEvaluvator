import { Routes, Route, Navigate } from 'react-router-dom'
import { InterviewProvider } from './context/InterviewContext'
import ProgressThread from './components/ProgressThread'
import UploadScreen from './components/UploadScreen'
import InterviewScreen from './components/InterviewScreen'
import ReportScreen from './components/ReportScreen'
import AdminDashboard from './components/AdminDashboard'
import AdminInterviewDetail from './components/AdminInterviewDetail'
import LogsScreen from './components/LogsScreen'

function App() {
  return (
    <InterviewProvider>
      <div className="min-h-screen relative flex">
        <ProgressThread />
        <main className="flex-1 ml-1 pl-4 sm:pl-8 flex flex-col min-h-screen">
          <Routes>
            <Route path="/" element={<Navigate to="/upload" replace />} />
            <Route path="/upload" element={<UploadScreen />} />
            <Route path="/interview" element={<InterviewScreen />} />
            <Route path="/report" element={<ReportScreen />} />
            <Route path="/admin" element={<Navigate to="/admin/interviews" replace />} />
            <Route path="/admin/interviews" element={<AdminDashboard />} />
            <Route path="/admin/interviews/:threadId" element={<AdminInterviewDetail />} />
            <Route path="/logs" element={<LogsScreen />} />
          </Routes>
        </main>
      </div>
    </InterviewProvider>
  )
}

export default App
