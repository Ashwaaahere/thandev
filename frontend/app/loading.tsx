'use client';

import { motion } from 'framer-motion';

export default function Loading() {
  return (
    <div className="grid min-h-screen place-items-center bg-slate-950 text-slate-100">
      <div className="text-center">
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-4xl font-extrabold tracking-tight"
        >
          <span className="bg-gradient-to-r from-cyan-400 to-indigo-500 bg-clip-text text-transparent">
            Thandev
          </span>
        </motion.div>

        <motion.div
          initial={{ width: 0 }}
          animate={{ width: '14rem' }}
          transition={{ duration: 1.2, repeat: Infinity, repeatType: 'mirror', ease: 'easeInOut' }}
          className="mx-auto mt-4 h-1 rounded-full bg-gradient-to-r from-cyan-400 to-indigo-500"
          style={{ boxShadow: '0 0 24px rgba(99,102,241,.35)' }}
        />

        <div className="mt-4 text-xs text-slate-400">
          initializing • fetching feeds • rendering
        </div>
      </div>
    </div>
  );
}
