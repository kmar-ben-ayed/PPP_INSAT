import { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar.jsx'
import ChatPage from './pages/ChatPage.jsx'
import AdminPage from './pages/AdminPage.jsx'
import BenchmarkPage from './pages/BenchmarkPage.jsx'
import { loadContext } from './lib/context.js'
import { getHealth } from './lib/api.js'

export default function App() {
  const [page, setPage] = useState('chat')
  const [approach, setApproach] = useState('A')
  const [context, setContext] = useState(loadContext)
  const [health, setHealth] = useState({ A: {}, B: {}, C: {} })
  const [lang, setLang] = useState(context.lang || 'fr')


  // Poll health for all 3 approaches every 30s
  useEffect(() => {
    async function checkAll() {
      const [a, b, c] = await Promise.all([
        getHealth('A'),
        getHealth('B'),
        getHealth('C'),
      ])
      setHealth({ A: a, B: b, C: c })
    }
    checkAll()
    const id = setInterval(checkAll, 30_000)
    return () => clearInterval(id)
  }, [])

  const pages = {
    chat:      <ChatPage approach={approach} context={context} lang={lang} setLang={setLang} />,
    admin:     <AdminPage context={context} setContext={setContext} lang={lang} />,
    benchmark: <BenchmarkPage approach={approach} lang={lang} />,
  }

  return (
    <div className="flex h-screen overflow-hidden bg-ink">
      <Sidebar
        page={page}
        setPage={setPage}
        approach={approach}
        setApproach={setApproach}
        health={health}
        lang={lang}
      />
      <main className="flex-1 overflow-hidden">
        {pages[page]}
      </main>
    </div>
  )
}
