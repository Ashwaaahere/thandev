'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useSession } from 'next-auth/react'
import { thandevFetchJSON } from '@/lib/thandevApi'

export default function PrivateBetaPage() {
  const { data: session } = useSession()
  const [status, setStatus] = useState<'idle' | 'pending' | 'sent' | 'error'>('idle')
  const [message, setMessage] = useState<string>('')
  const [showWelcome, setShowWelcome] = useState(false)

  const requestAccess = async () => {
    setStatus('pending')
    setMessage('')
    try {
      await thandevFetchJSON('/api/access/request', session, { method: 'POST' })
      setStatus('sent')
      setMessage('Request sent. We will notify you once approved.')
    } catch (err) {
      console.error(err)
      setStatus('error')
      setMessage(err instanceof Error ? err.message : 'Failed to send request')
    }
  }

  const isApproved = session?.user?.isApproved
  const isAdmin = session?.user?.isAdmin
  const greetedKey = 'thandev_first_approved_greeted'

  useEffect(() => {
    if ((isApproved || isAdmin) && typeof window !== 'undefined') {
      const already = window.localStorage.getItem(greetedKey)
      if (!already) {
        setShowWelcome(true)
        window.localStorage.setItem(greetedKey, '1')
      }
    }
  }, [isApproved, isAdmin])

  return (
    <div className="max-w-xl mx-auto py-16 px-4">
      <h1 className="text-3xl font-semibold mb-4">Private beta access required</h1>
      <p className="mb-6 text-gray-300">
        You&apos;re signed in, but your account hasn&apos;t been approved yet.
        Please request access and an admin will review your request.
      </p>

      {isAdmin ? (
        <div className="space-y-3">
          <p className="text-green-400">You are an admin.</p>
          <Link
            href="/admin"
            className="inline-block bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded"
          >
            Go to Admin
          </Link>
        </div>
      ) : isApproved ? (
        <div className="space-y-3">
          {showWelcome && (
            <div className="text-lg text-emerald-300 animate-pulse">
              🎉 Welcome aboard! Your access is live.
            </div>
          )}
          <p className="text-green-400">Your account is already approved.</p>
          <Link
            href="/dashboard"
            className="inline-block bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded"
          >
            Go to dashboard
          </Link>
        </div>
      ) : (
        <button
          onClick={requestAccess}
          disabled={status === 'pending' || status === 'sent'}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded disabled:opacity-60"
        >
          {status === 'pending' ? 'Sending...' : status === 'sent' ? 'Request sent' : 'Request access'}
        </button>
      )}

      {message && <p className="mt-4 text-sm text-gray-200">{message}</p>}
    </div>
  )
}

