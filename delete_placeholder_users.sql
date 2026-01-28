-- Delete placeholder users (those with @example.com emails)
-- These are test/placeholder accounts that shouldn't be in production

DELETE FROM users 
WHERE email LIKE '%@example.com';

-- Verify deletion (should return 0 rows)
SELECT id, email, username FROM users WHERE email LIKE '%@example.com';

