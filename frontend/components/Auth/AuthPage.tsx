'use client';

import { useState, useEffect } from 'react';
import SigninForm from './SigninForm';
import SignupForm from './SignupForm';

export default function AuthPage() {
  const [isSignup, setIsSignup] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);

  const switchMode = () => {
    setIsAnimating(true);
    setTimeout(() => {
      setIsSignup(!isSignup);
      setIsAnimating(false);
    }, 300);
  };

  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* Animated Background */}
      <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
        {/* Floating Particles */}
        <div className="absolute inset-0">
          {[...Array(50)].map((_, i) => (
            <div
              key={i}
              className="absolute w-1 h-1 bg-cyan-400 rounded-full animate-pulse"
              style={{
                left: `${Math.random() * 100}%`,
                top: `${Math.random() * 100}%`,
                animationDelay: `${Math.random() * 3}s`,
                animationDuration: `${2 + Math.random() * 3}s`
              }}
            />
          ))}
        </div>

        {/* Gradient Orbs */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-gradient-to-r from-cyan-500/20 to-blue-500/20 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-gradient-to-r from-purple-500/20 to-pink-500/20 rounded-full blur-3xl animate-pulse" />
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-gradient-to-r from-green-500/20 to-cyan-500/20 rounded-full blur-3xl animate-pulse" />

        {/* Grid Pattern */}
        <div className="absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg%20width%3D%2260%22%20height%3D%2260%22%20viewBox%3D%220%200%2060%2060%22%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%3E%3Cg%20fill%3D%22none%22%20fill-rule%3D%22evenodd%22%3E%3Cg%20fill%3D%22%239C92AC%22%20fill-opacity%3D%220.05%22%3E%3Ccircle%20cx%3D%2230%22%20cy%3D%2230%22%20r%3D%221%22/%3E%3C/g%3E%3C/g%3E%3C/svg%3E')] opacity-30" />
      </div>

      {/* Main Content */}
      <div className="relative z-10 min-h-screen flex items-center justify-center px-4 py-8">
        <div className="w-full max-w-md">
          {/* Logo and Title */}
          <div className="text-center mb-12">
            <div className="flex items-center justify-center gap-3 mb-6">
              <div className="relative">
                <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-cyan-400 to-indigo-500 shadow-lg shadow-cyan-500/25" />
                <div className="absolute inset-0 h-12 w-12 rounded-xl bg-gradient-to-br from-cyan-400 to-indigo-500 animate-ping opacity-20" />
              </div>
              <span className="text-3xl font-bold tracking-tight bg-gradient-to-r from-cyan-400 to-indigo-500 bg-clip-text text-transparent">
                Thandev
              </span>
            </div>
            <h1 className="text-2xl font-bold text-white mb-2">
              {isSignup ? 'Join the Future' : 'Welcome Back'}
            </h1>
            <p className="text-slate-400">
              {isSignup ? 'Create your account and unlock unlimited security scanning' : 'Sign in to continue your security journey'}
            </p>
          </div>

          {/* Auth Card */}
          <div className="relative">
            {/* Card Background with Glow */}
            <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/20 to-purple-500/20 rounded-3xl blur-xl" />
            <div className="relative bg-slate-800/50 backdrop-blur-xl border border-slate-700/50 rounded-3xl p-8 shadow-2xl">
              {/* Tab Switcher */}
              <div className="flex mb-8 bg-slate-700/30 rounded-2xl p-1">
                <button
                  onClick={() => isSignup && !isAnimating && switchMode()}
                  className={`flex-1 py-3 px-4 rounded-xl font-semibold transition-all duration-300 ${
                    !isSignup
                      ? 'bg-gradient-to-r from-cyan-500 to-blue-500 text-white shadow-lg'
                      : 'text-slate-400 hover:text-white'
                  }`}
                  disabled={isAnimating}
                >
                  Sign In
                </button>
                <button
                  onClick={() => !isSignup && !isAnimating && switchMode()}
                  className={`flex-1 py-3 px-4 rounded-xl font-semibold transition-all duration-300 ${
                    isSignup
                      ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg'
                      : 'text-slate-400 hover:text-white'
                  }`}
                  disabled={isAnimating}
                >
                  Sign Up
                </button>
              </div>

              {/* Form Container */}
              <div className="relative overflow-hidden">
                <div className={`transition-all duration-500 ease-in-out ${isAnimating ? 'opacity-0 scale-95' : 'opacity-100 scale-100'}`}>
                  {isSignup ? (
                    <SignupForm onSuccess={() => window.location.href = '/scan'} />
                  ) : (
                    <SigninForm onSuccess={() => window.location.href = '/scan'} />
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Features List */}
          <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex items-center gap-3 text-slate-400">
              <div className="w-2 h-2 bg-cyan-400 rounded-full animate-pulse" />
              <span className="text-sm">Unlimited Security Scans</span>
            </div>
            <div className="flex items-center gap-3 text-slate-400">
              <div className="w-2 h-2 bg-purple-400 rounded-full animate-pulse" />
              <span className="text-sm">Advanced Vulnerability Detection</span>
            </div>
            <div className="flex items-center gap-3 text-slate-400">
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
              <span className="text-sm">Real-time Threat Intelligence</span>
            </div>
            <div className="flex items-center gap-3 text-slate-400">
              <div className="w-2 h-2 bg-pink-400 rounded-full animate-pulse" />
              <span className="text-sm">Professional Security Reports</span>
            </div>
          </div>

          {/* Security Badge */}
          <div className="mt-8 text-center">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-full text-slate-400 text-sm">
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
              <span>Enterprise-grade Security</span>
            </div>
          </div>
        </div>
      </div>

      {/* Floating Elements */}
      <div className="absolute top-20 left-20 w-4 h-4 bg-cyan-400/30 rounded-full animate-bounce" style={{ animationDelay: '0s' }} />
      <div className="absolute top-40 right-32 w-3 h-3 bg-purple-400/30 rounded-full animate-bounce" style={{ animationDelay: '1s' }} />
      <div className="absolute bottom-32 left-32 w-5 h-5 bg-green-400/30 rounded-full animate-bounce" style={{ animationDelay: '2s' }} />
      <div className="absolute bottom-20 right-20 w-2 h-2 bg-pink-400/30 rounded-full animate-bounce" style={{ animationDelay: '0.5s' }} />
    </div>
  );
}
