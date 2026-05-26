-- Add per-answer video segment timestamp columns to interview_answers
-- These are set by the WebSocket handler to enable per-question video analysis.

ALTER TABLE interview_answers ADD COLUMN IF NOT EXISTS video_start_second FLOAT;
ALTER TABLE interview_answers ADD COLUMN IF NOT EXISTS video_end_second   FLOAT;
