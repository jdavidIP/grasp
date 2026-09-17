import { BrowserRouter, Route, Routes } from 'react-router'
import { LibraryPage } from './pages/LibraryPage'
import { VideoDetailPage } from './pages/VideoDetailPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LibraryPage />} />
        <Route path="/videos/:id" element={<VideoDetailPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
