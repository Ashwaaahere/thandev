'use client';

import { useState } from 'react';

export default function SigninForm() {
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
        
        // Redirect to scan page after success
        setTimeout(() => {
          window.location.href = '/scan';
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
      <div className="relative overflow-hidden rounded-2xl border border-green-200/50 bg-gradient-to-br from-green-50/50 to-green-100/30 p-8 backdrop-blur-sm dark:border-green-800/50 dark:from-green-950/40 dark:to-green-900/20">
        <div className="absolute inset-0 bg-gradient-to-br from-green-500/5 to-transparent" />
        <div className="relative z-10 text-center">
          <div className="mb-4 flex items-center justify-center gap-3">
            <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
            <span className="text-sm font-semibold text-green-600 dark:text-green-400">SUCCESS</span>
          </div>
          <h2 className="text-xl font-bold text-green-800 dark:text-green-200 mb-2">Welcome Back!</h2>
          <p className="text-green-600 dark:text-green-300 mb-4">
            You're now signed in and have unlimited access to our security scanning tools.
          </p>
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-green-500 mx-auto"></div>
          <p className="text-sm text-green-600 dark:text-green-300 mt-2">Redirecting to scanner...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-8 shadow-lg">
      <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent" />
      
      <div className="relative z-10">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Email */}
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-[var(--fg)] mb-2">
              Email Address
            </label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--fg)] placeholder-[var(--muted)] focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
              placeholder="Enter your email address"
            />
          </div>

          {/* Password */}
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-[var(--fg)] mb-2">
              Password
            </label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--fg)] placeholder-[var(--muted)] focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
              placeholder="Enter your password"
            />
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20">
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-3 px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white font-semibold rounded-lg hover:from-blue-600 hover:to-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-lg hover:shadow-xl"
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
        <div className="mt-6 p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
          <div className="flex items-start gap-3">
            <div className="h-5 w-5 text-yellow-500 mt-0.5">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <h4 className="font-medium text-yellow-700 dark:text-yellow-300 mb-1">Demo Mode</h4>
              <p className="text-sm text-yellow-600 dark:text-yellow-400">
                Enter any email and password to sign in. In production, this would validate against your backend.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
