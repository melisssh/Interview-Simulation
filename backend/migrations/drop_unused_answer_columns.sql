-- Drop unused columns from interview_answers table
-- These columns were removed from the SQLAlchemy model and are no longer used.

ALTER TABLE interview_answers DROP COLUMN IF EXISTS keyword_match_score;
ALTER TABLE interview_answers DROP COLUMN IF EXISTS volume_stability_score;
ALTER TABLE interview_answers DROP COLUMN IF EXISTS tone_variation_score;
ALTER TABLE interview_answers DROP COLUMN IF EXISTS sentiment_score;
ALTER TABLE interview_answers DROP COLUMN IF EXISTS engagement_score;
ALTER TABLE interview_answers DROP COLUMN IF EXISTS confidence_tone_score;
