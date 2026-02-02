-- Fix admin user after Supabase migration
-- This script updates the user record with the correct GitHub IDs
-- Replace 'd36da182-2f87-4c52-9ab2-b8a7dcd28bcf' with your actual user ID if different

-- Update user with GitHub ID 97579623 (first superadmin)
UPDATE users 
SET 
    external_provider = 'github',
    external_user_id = '97579623',
    is_admin = true,
    is_approved = true
WHERE id = 'd36da182-2f87-4c52-9ab2-b8a7dcd28bcf'
  AND (external_user_id IS NULL OR external_user_id = '');

-- If you have multiple admin users, you can add more UPDATE statements:
-- UPDATE users 
-- SET 
--     external_provider = 'github',
--     external_user_id = '4708392',
--     is_admin = true,
--     is_approved = true
-- WHERE email = 'your-email@example.com'
--   AND (external_user_id IS NULL OR external_user_id = '');



