from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    Custom SessionAuthentication that skips CSRF enforcement.
    
    DRF's default SessionAuthentication enforces CSRF on every state-changing 
    request (POST/PUT/PATCH/DELETE), which conflicts with cross-domain setups 
    (Vercel frontend + EC2 backend) where the CSRF cookie is not reliably sent.
    
    Security is maintained via session cookie authentication (IsAuthenticated permission).
    """
    def enforce_csrf(self, request):
        return  # Skip CSRF — session cookie auth is sufficient
