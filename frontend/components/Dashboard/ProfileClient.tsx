'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import DashboardHeader from './DashboardHeader';
import DashboardSidebar from './DashboardSidebar';

interface ProfileClientProps {
  user: any;
}

export default function ProfileClient({ user }: ProfileClientProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('profile');
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({
    name: user?.name || '',
    email: user?.email || '',
    company: user?.company || '',
    role: user?.role || '',
    bio: user?.bio || '',
    location: user?.location || '',
    website: user?.website || '',
    twitter: user?.twitter || '',
    linkedin: user?.linkedin || '',
  });

  const handleSave = () => {
    // In a real app, this would make an API call
    console.log('Saving profile:', formData);
    setIsEditing(false);
  };

  const tabs = [
    { id: 'profile', name: 'Profile', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
    { id: 'security', name: 'Security', icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z' },
    { id: 'notifications', name: 'Notifications', icon: 'M15 17h5l-5 5v-5zM4.5 5.5a3 3 0 013-3h9a3 3 0 013 3v9a3 3 0 01-3 3h-9a3 3 0 01-3-3v-9z' },
    { id: 'billing', name: 'Billing', icon: 'M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z' },
  ];

  return (
    <div className="flex h-screen overflow-hidden">
      <DashboardSidebar 
        isOpen={sidebarOpen} 
        onClose={() => setSidebarOpen(false)} 
        showLogo={!sidebarOpen}
      />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <DashboardHeader 
          user={user} 
          onMenuClick={() => setSidebarOpen(true)}
          showLogo={sidebarOpen}
        />
        
        <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
          <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--fg)' }}>Profile Settings</h1>
        <p style={{ color: 'var(--muted)' }}>Manage your account settings and preferences</p>
      </div>

      {/* Tabs */}
      <div className="mb-8">
        <div className="border-b" style={{ borderColor: 'var(--border)' }}>
          <nav className="-mb-px flex space-x-8">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2 transition-colors ${activeTab === tab.id
                    ? 'border-blue-500'
                    : 'border-transparent hover:border-gray-300'
                  }`}
                style={{
                  color: activeTab === tab.id ? 'var(--brand)' : 'var(--muted)',
                  borderColor: activeTab === tab.id ? 'var(--brand)' : 'transparent'
                }}
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={tab.icon} />
                </svg>
                {tab.name}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Tab Content */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="space-y-6"
      >
        {activeTab === 'profile' && (
          <div className="glass-card p-6 rounded-xl border" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
            {/* Profile Header */}
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center space-x-4">
                <div className="h-20 w-20 rounded-full flex items-center justify-center text-2xl font-bold text-white shadow-lg" style={{ background: 'var(--brand)' }}>
                  {user.name?.charAt(0)?.toUpperCase() || user.email?.charAt(0)?.toUpperCase() || 'U'}
                </div>
                <div>
                  <h2 className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>{user.name || 'User'}</h2>
                  <p style={{ color: 'var(--muted)' }}>{user.email}</p>
                  <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>Member since {new Date().getFullYear()}</p>
                </div>
              </div>
              <button
                onClick={() => setIsEditing(!isEditing)}
                className="px-4 py-2 rounded-lg font-medium transition-all hover:shadow-lg"
                style={{
                  background: isEditing ? 'var(--surface-2)' : 'var(--brand)',
                  color: isEditing ? 'var(--fg)' : 'white'
                }}
              >
                {isEditing ? 'Cancel' : 'Edit Profile'}
              </button>
            </div>

            {/* Profile Form */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {[
                { label: 'Full Name', key: 'name', type: 'text' },
                { label: 'Email', key: 'email', type: 'email' },
                { label: 'Company', key: 'company', type: 'text' },
                { label: 'Role', key: 'role', type: 'text' },
                { label: 'Location', key: 'location', type: 'text' },
                { label: 'Website', key: 'website', type: 'url' },
              ].map((field) => (
                <div key={field.key}>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>{field.label}</label>
                  <input
                    type={field.type}
                    value={formData[field.key as keyof typeof formData]}
                    onChange={(e) => setFormData({ ...formData, [field.key]: e.target.value })}
                    disabled={!isEditing}
                    className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 transition-all"
                    style={{
                      borderColor: 'var(--border)',
                      background: 'var(--bg)',
                      color: 'var(--fg)'
                    }}
                  />
                </div>
              ))}

              <div className="md:col-span-2">
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>Bio</label>
                <textarea
                  value={formData.bio}
                  onChange={(e) => setFormData({ ...formData, bio: e.target.value })}
                  disabled={!isEditing}
                  rows={4}
                  className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 transition-all"
                  style={{
                    borderColor: 'var(--border)',
                    background: 'var(--bg)',
                    color: 'var(--fg)'
                  }}
                />
              </div>
            </div>

            {/* Save Button */}
            {isEditing && (
              <div className="flex justify-end mt-6 pt-6 border-t" style={{ borderColor: 'var(--border)' }}>
                <button
                  onClick={handleSave}
                  className="px-6 py-2 rounded-lg font-medium text-white transition-all hover:shadow-lg transform hover:-translate-y-0.5"
                  style={{ background: 'var(--brand)' }}
                >
                  Save Changes
                </button>
              </div>
            )}
          </div>
        )}

        {/* Other tabs placeholders with consistent styling */}
        {['security', 'notifications', 'billing'].includes(activeTab) && (
          <div className="glass-card p-8 rounded-xl border text-center" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
            <div className="inline-flex items-center justify-center p-4 rounded-full mb-4" style={{ background: 'var(--surface-2)' }}>
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: 'var(--brand)' }}>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <h3 className="text-xl font-bold mb-2" style={{ color: 'var(--fg)' }}>Coming Soon</h3>
            <p style={{ color: 'var(--muted)' }}>This feature is currently under development.</p>
          </div>
        )}
      </motion.div>
          </div>
        </main>
      </div>
    </div>
  );
}
