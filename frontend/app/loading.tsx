'use client';
import { motion } from 'framer-motion';

export default function Loading() {
  return (
    <div className="grid min-h-[60vh] place-items-center">
      <div className="card w-full max-w-xl p-8 text-center shadow-sm">
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-3xl font-extrabold tracking-tight"
        >
          <span className="bg-gradient-to-r from-cyan-400 to-indigo-500 bg-clip-text text-transparent">
            Thandev
          </span>
        </motion.div>

        <motion.div
          initial={{ width: 0 }}
          animate={{ width: '12rem' }}
          transition={{ duration: 1.2, repeat: Infinity, repeatType: 'mirror', ease: 'easeInOut' }}
          className="mx-auto mt-4 h-1 rounded-full bg-gradient-to-r from-cyan-400 to-indigo-500"
          style={{ boxShadow: '0 0 24px rgba(99,102,241,.35)' }}
        />

        <div className="mt-4 text-xs muted">initializing • fetching feeds • rendering</div>
      </div>
    </div>
  );
}
