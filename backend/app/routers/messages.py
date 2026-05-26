MSG = {
    "login_required": "Login required",
    "invalid_token": "Invalid token",
    "token_expired": "Token expired",
    "user_not_found": "User not found",
    "wrong_password": "Wrong password",
    "invalid_credentials": "Invalid email or password.",
    "email_not_verified": "Email not verified. Please check your inbox.",
    "password_too_short": "Password must be at least 8 characters.",
    "email_exists": "An account with this email already exists. Please log in.",
    "current_password_wrong": "Current password is wrong.",
    "new_password_too_short": "New password must be at least 8 characters.",
    "invalid_reset_link": "This password reset link is invalid or expired.",
    "invalid_verification_code": "Invalid verification code.",
    "verification_link_expired": "Verification link has expired.",
    "cv_required": "You must upload a CV before creating an interview.",
    "fields_required": "Company, department, position and sector are required.",
    "interview_not_found": "Interview not found",
    "access_denied": "You do not have access to this interview",
    "invalid_status": "Invalid interview status",
    "not_authorized": "You are not authorized for this action",
    "not_preparation_failed": "This interview is not eligible for retry",
    "analysis_not_ready": "Analysis results are not ready yet",
    "no_answer_data": "No answer data found",
    "ws_not_ready": "Interview is not ready yet. Please wait.",
    "ws_prep_failed": "Interview preparation failed. Please try again.",
    "ws_completed": "Interview completed. Thank you.",
}


def _(key: str, lang: str = "en") -> str:
    return MSG.get(key, key)


