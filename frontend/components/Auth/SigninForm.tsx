'use client';

import { useState } from 'react';

interface SigninFormProps {
  onSuccess?: () => void;
}

export default function SigninForm({ onSuccess }: SigninFormProps) {
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      // In a real app, this would validate credentials with your backend
      // For demo purposes, we'll accept any email/password combination
      if (formData.email && formData.password) {
        // Store user session
        localStorage.setItem('thandev-user', JSON.stringify({
          id: Date.now().toString(),
          email: formData.email,
          signedInAt: new Date().toISOString()
        }));

        // Clear scan limit for authenticated users
        localStorage.removeItem('thandev-scan-limit');
        
        setSuccess(true);
        
        // Call success callback or redirect
        setTimeout(() => {
          if (onSuccess) {
            onSuccess();
          } else {
            window.location.href = '/scan';
          }
        }, 2000);
      } else {
        setError('Please enter both email and password');
      }
      
    } catch (err) {
      setError('Invalid credentials. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="relative overflow-hidden rounded-2xl border border-green-500/30 bg-gradient-to-br from-green-500/10 to-emerald-500/10 p-8 backdrop-blur-sm">
        <div className="absolute inset-0 bg-gradient-to-br from-green-500/5 to-transparent" />
        <div className="relative z-10 text-center">
          <div className="mb-4 flex items-center justify-center gap-3">
            <div className="h-2 w-2 rounded-full bg-green-400 animate-pulse" />
            <span className="text-sm font-semibold text-green-400">SUCCESS</span>
          </div>
          <h2 className="text-xl font-bold text-white mb-2">Welcome Back!</h2>
          <p className="text-slate-300 mb-4">
            You're now signed in and have unlimited access to our security scanning tools.
          </p>
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-green-400 mx-auto"></div>
          <p className="text-sm text-slate-300 mt-2">Redirecting to scanner...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Email */}
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-slate-300 mb-2">
            Email Address
          </label>
          <div className="relative">
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 rounded-xl border border-slate-600 bg-slate-700/50 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all duration-200 backdrop-blur-sm"
              placeholder="Enter your email address"
            />
            <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-cyan-500/10 to-blue-500/10 opacity-0 focus-within:opacity-100 transition-opacity duration-200 pointer-events-none" />
          </div>
        </div>

        {/* Password */}
        <div>
          <label htmlFor="password" className="block text-sm font-medium text-slate-300 mb-2">
            Password
          </label>
          <div className="relative">
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 rounded-xl border border-slate-600 bg-slate-700/50 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all duration-200 backdrop-blur-sm"
              placeholder="Enter your password"
            />
            <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-cyan-500/10 to-blue-500/10 opacity-0 focus-within:opacity-100 transition-opacity duration-200 pointer-events-none" />
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 backdrop-blur-sm">
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading}
          className="w-full flex items-center justify-center gap-3 px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-500 text-white font-semibold rounded-xl hover:from-cyan-600 hover:to-blue-600 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-lg hover:shadow-xl hover:shadow-cyan-500/25"
        >
          {loading ? (
            <>
              <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent"></div>
              <span>Signing In...</span>
            </>
          ) : (
            <>
              <div className="h-5 w-5">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                </svg>
              </div>
              <span>Sign In</span>
            </>
          )}
        </button>
      </form>

      {/* Demo Notice */}
      <div className="p-4 rounded-xl bg-yellow-500/10 border border-yellow-500/30 backdrop-blur-sm">
        <div className="flex items-start gap-3">
          <div className="h-5 w-5 text-yellow-400 mt-0.5">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <h4 className="font-medium text-yellow-300 mb-1">Demo Mode</h4>
            <p className="text-sm text-slate-400">
              Enter any email and password to sign in. In production, this would validate against your backend.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
