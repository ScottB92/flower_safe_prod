import { useState, useEffect } from 'react'
import axios from 'axios'
import { motion, AnimatePresence } from 'framer-motion'
import { FaLeaf, FaCheckCircle, FaExclamationTriangle } from 'react-icons/fa'

const API_URL = import.meta.env.VITE_API_URL || 'https://flower-safety-api2.vercel.app/'

const SUGGESTIONS = [
  'Roses','Lilies','Tulip','Sunflowers','Peonies','Lavender','Daisies','Orchids','Snapdragons','Statice','Lisianthus'
]

function Header() {
  return (
    <header className="py-8">
      <div className="container px-6">
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-xl bg-white shadow">
            <FaLeaf className="text-3xl text-brand-rose" />
          </div>
          <div>
            <h1 className="text-3xl font-extrabold text-brand-rose">Pet-Safe Flower Checker</h1>
            <p className="text-sm text-gray-600">Quickly check whether flowers are safe for cats and dogs.</p>
          </div>
        </div>
      </div>
    </header>
  )
}

function SuggestionPills({onPick}) {
  return (
    <div className="flex gap-2 flex-wrap mt-3">
      {SUGGESTIONS.map(s => (
        <button key={s} onClick={() => onPick(s)}
          className="px-3 py-1 bg-white text-sm rounded-full shadow text-gray-700 hover:bg-brand-cream transition">
          {s}
        </button>
      ))}
    </div>
  )
}

export default function App(){
  const [q, setQ] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [recent, setRecent] = useState([])

  useEffect(() => {
    const stored = localStorage.getItem('recentFlowers')
    if (stored) setRecent(JSON.parse(stored))
  }, [])

  const pick = (name) => {
    setQ(name)
    check(name)
  }

  const check = async (name) => {
    const flower = (name || q || '').trim()
    if (!flower) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await axios.post(new URL('/flower-check', API_URL).toString(), { flower })
      setResult(res.data)
      const next = [res.data.flower || flower, ...recent.filter(r=>r !== flower)].slice(0,6)
      setRecent(next)
      localStorage.setItem('recentFlowers', JSON.stringify(next))
    } catch(err){
      console.error(err)
      setError(err.response?.data?.error || 'Network error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <Header />
      <main className="container px-6">
        <section className="bg-white rounded-3xl shadow p-8">
          <label className="block text-sm font-medium text-gray-700">Check a flower</label>
          <div className="mt-4 flex gap-3">
            <input value={q} onChange={(e)=>setQ(e.target.value)}
              placeholder="e.g., Roses" className="flex-1 p-3 rounded-lg border focus:outline-none focus:ring-2 focus:ring-brand-pink" />
            <motion.button
              whileTap={{ scale: 0.98 }}
              onClick={()=>check()}
              disabled={loading}
              className="px-6 py-3 bg-brand-rose text-white rounded-lg shadow-md disabled:opacity-60"
            >
              {loading ? 'Checking...' : 'Check'}
            </motion.button>
          </div>

          <SuggestionPills onPick={pick} />

          <div className="mt-6 flex flex-col gap-4">
            <AnimatePresence>
            {error && (
              <motion.div initial={{opacity:0,y:6}} animate={{opacity:1,y:0}} exit={{opacity:0}} className="p-3 bg-red-50 text-red-700 rounded">
                {error}
              </motion.div>
            )}

            {result && (
              <motion.div initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} exit={{opacity:0}} className="p-6 bg-gradient-to-r from-white to-brand-cream rounded-2xl shadow-md border">
                <div className="flex items-start gap-4">
                  <div className="pt-1">
                    {result.verified ? (
                      <FaCheckCircle className="text-green-500 text-3xl" />
                    ) : (
                      <FaExclamationTriangle className="text-yellow-600 text-3xl" />
                    )}
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-800">Result for: {result.flower}</h3>
                    <p className="mt-2 text-gray-700">{result.message}</p>
                    {!result.verified && result.note && (
                      <p className="mt-2 text-sm text-yellow-900">{result.note}</p>
                    )}
                    <p className="mt-3 text-xs text-gray-500">Source: {result.source}</p>
                  </div>
                </div>
              </motion.div>
            )}
            </AnimatePresence>

            {recent.length > 0 && (
              <div className="text-sm text-gray-600">
                Recent checks: {recent.join(', ')}
              </div>
            )}
          </div>
        </section>

        <section className="mt-8 text-sm text-gray-600">
          <h4 className="font-semibold">About</h4>
          <p className="mt-2">This tool uses a RAG-enabled API to verify whether common flowers are safe for cats and dogs. Verified results come from the shop's curated database; unverified results are best-effort from an LLM and include a veterinarian recommendation.</p>
        </section>

        <footer className="mt-12 py-8 text-center text-xs text-gray-400">
          Made with care • Remember: if in doubt, contact your vet.
        </footer>
      </main>
    </div>
  )
}
