import logging
import re
import requests
import socket
from datetime import datetime, timedelta
from time import sleep

from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from django.dispatch import Signal, receiver
from django.contrib.auth.signals import user_logged_in, user_login_failed

from user_agents import parse

# ------------------------------------------------------------------------------
# Custom Signal for Unauthorized Access
# ------------------------------------------------------------------------------
unauthorized_access = Signal()

# ------------------------------------------------------------------------------
# Logger Definitions
# ------------------------------------------------------------------------------
auth_logger = logging.getLogger('django.security.Authentication')
unauthorized_logger = logging.getLogger('unauthorized.access')
blacklist_logger = logging.getLogger('blacklist')

# ------------------------------------------------------------------------------
# Utility Functions
# ------------------------------------------------------------------------------
def get_client_ip(request):
    """Return the client IP address from the request headers."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

def get_ip_location(ip, retries=3, delay=1):
    """Retrieve IP location data from ipinfo.io with simple retry logic."""
    for _ in range(retries):
        try:
            response = requests.get(f'https://ipinfo.io/{ip}/json', timeout=3)
            ip_data = response.json()
            return {
                'city': ip_data.get('city', 'Unknown'),
                'region': ip_data.get('region', 'Unknown'),
                'country': ip_data.get('country', 'Unknown'),
                'org': ip_data.get('org', 'Unknown'),
                'isp': ip_data.get('org', 'Unknown')
            }
        except requests.RequestException as e:
            logging.error(f"Error fetching IP location for {ip}: {e}")
            sleep(delay)
    return {'city': 'Unknown', 'region': 'Unknown', 'country': 'Unknown', 'org': 'Unknown', 'isp': 'Unknown'}

def get_user_agent_info(user_agent_string):
    """Parse the user agent string and return a dict of OS, browser, device info."""
    user_agent = parse(user_agent_string)
    application = 'Unknown Application'
    # Simple application detection logic
    if 'Unity' in user_agent_string:
        application = 'Unity Game Engine'
    elif 'Unreal' in user_agent_string:
        application = 'Unreal Engine'
    elif 'Android' in user_agent_string:
        application = 'Android APK'
    elif 'iPhone' in user_agent_string or 'iOS' in user_agent_string:
        application = 'iPhone App'
    elif 'Huawei' in user_agent_string:
        application = 'Huawei App'
    elif 'SmartTV' in user_agent_string or 'TV' in user_agent_string:
        application = 'TV OS'
    elif 'Windows' in user_agent_string:
        application = 'Windows App'
    elif 'Macintosh' in user_agent_string or 'Mac OS' in user_agent_string:
        application = 'Mac OS App'
    elif 'Linux' in user_agent_string:
        application = 'Linux App'
    elif 'Chrome OS' in user_agent_string:
        application = 'Chrome OS App'
    elif 'Firefox' in user_agent_string:
        application = 'Firefox Browser'
    elif 'Safari' in user_agent_string:
        application = 'Safari Browser'
    elif 'Edge' in user_agent_string:
        application = 'Edge Browser'
    elif 'Opera' in user_agent_string:
        application = 'Opera Browser'
    elif 'SamsungBrowser' in user_agent_string:
        application = 'Samsung Browser'
    return {
        'os': user_agent.os.family,
        'browser': user_agent.browser.family,
        'device': user_agent.device.family,
        'brand': user_agent.device.brand,
        'model': user_agent.device.model,
        'application': application
    }

def get_reverse_dns(ip):
    """Return the reverse DNS lookup for an IP address."""
    try:
        return socket.gethostbyaddr(ip)[0]
    except (socket.herror, socket.gaierror):
        return 'Unknown Hostname'

# ------------------------------------------------------------------------------
# Security Middleware
# ------------------------------------------------------------------------------
# SQL Injection detection constants
SQL_INJECTION_PATTERNS = [
    r"(%27)|(')|(--)|(%23)|(#)",
    r"\b(SELECT|UPDATE|DELETE|INSERT|ALTER|DROP|CREATE|REPLACE|TRUNCATE)\b",
    r"\b(OR|AND)\b\s+\d+\s*=\s*\d+"
]
BLOCK_THRESHOLD = 100
ATTEMPT_PERIOD = 3600  # 1 hour in seconds
BLOCK_DURATIONS = [24 * 3600, 48 * 3600, 72 * 3600]

class SecurityMiddleware(MiddlewareMixin):
    """
    This middleware combines the following functions:
      - SQL injection detection and IP blocking
      - Redirecting 403/404 responses to the home page (avoiding redirect loops)
      - Emitting a signal for unauthorized access for logging purposes
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.home_url = reverse('main:home')
        super().__init__(get_response)

    def process_request(self, request):
        # --- SQL Injection Detection & Blocking ---
        ip = get_client_ip(request)
        blocked_data = cache.get(f'blocked_{ip}')
        if blocked_data:
            block_count, block_expiry = blocked_data
            if datetime.now() < block_expiry:
                return HttpResponseForbidden("Your IP is temporarily blocked due to suspicious activity.")

        if self._is_suspicious(request):
            self._track_attempts(ip)
            if self._should_block_ip(ip):
                self._block_ip(ip)
                return HttpResponseForbidden("Your IP is temporarily blocked due to suspicious activity.")
            # Emit signal for suspicious request
            unauthorized_access.send(sender=self.__class__, request=request, reason="SQL injection attempt")
        # Continue processing the request normally
        return None

    def process_response(self, request, response):
        # --- Redirect on 403/404 Errors ---
        if response.status_code in (403, 404) and request.path != self.home_url:
            reason = "Forbidden" if response.status_code == 403 else "Not Found"
            unauthorized_access.send(sender=self.__class__, request=request, reason=reason)
            return redirect(self.home_url)
        return response

    def _is_suspicious(self, request):
        """Check if the request URL matches any SQL injection pattern."""
        full_path = request.get_full_path()
        for pattern in SQL_INJECTION_PATTERNS:
            if re.search(pattern, full_path, re.IGNORECASE):
                return True
        return False

    def _track_attempts(self, ip):
        """Track the number of suspicious attempts for a given IP."""
        count, last_attempt = cache.get(f'attempts_{ip}', (0, None))
        if last_attempt and (datetime.now() - last_attempt).total_seconds() > ATTEMPT_PERIOD:
            count = 0
        count += 1
        cache.set(f'attempts_{ip}', (count, datetime.now()), timeout=ATTEMPT_PERIOD)
        logging.debug(f"Tracking attempts for IP {ip}: count={count}")

    def _should_block_ip(self, ip):
        """Determine if the IP has exceeded the allowed number of attempts."""
        count, _ = cache.get(f'attempts_{ip}', (0, None))
        logging.debug(f"Block check for IP {ip}: count={count}, threshold={BLOCK_THRESHOLD}")
        return count >= BLOCK_THRESHOLD

    def _block_ip(self, ip):
        """Block the IP for a duration based on the number of previous blocks."""
        block_data = cache.get(f'blocked_{ip}')
        if not isinstance(block_data, tuple) or len(block_data) != 2:
            block_data = (0, datetime.now())
        block_count, _ = block_data
        block_duration = BLOCK_DURATIONS[min(block_count, len(BLOCK_DURATIONS) - 1)]
        block_expiry = datetime.now() + timedelta(seconds=block_duration)
        cache.set(f'blocked_{ip}', (block_count + 1, block_expiry), timeout=block_duration)
        cache.delete(f'attempts_{ip}')  # Reset attempt count after blocking
        blacklist_logger.warning(f"Blocked IP {ip} for {block_duration} seconds (block count: {block_count + 1}).")
        logging.debug(f"IP {ip} blocked for {block_duration} seconds.")

# ------------------------------------------------------------------------------
# Signal Receivers for Logging
# ------------------------------------------------------------------------------
@receiver(unauthorized_access)
def log_unauthorized_access(sender, request, reason, **kwargs):
    ip = get_client_ip(request)
    ip_location = get_ip_location(ip)
    user_agent_info = get_user_agent_info(request.META.get('HTTP_USER_AGENT', ''))
    reverse_dns = get_reverse_dns(ip)
    message = (
        f"Unauthorized access attempt: IP: {ip}, Reverse DNS: {reverse_dns}, "
        f"Location: {ip_location.get('city')}, {ip_location.get('region')}, {ip_location.get('country')}, "
        f"ISP: {ip_location.get('isp')}, OS: {user_agent_info['os']}, "
        f"App: {user_agent_info['application']}, Browser: {user_agent_info['browser']}, "
        f"Device: {user_agent_info['device']}, URL: {request.get_full_path()}, Reason: {reason}"
    )
    unauthorized_logger.warning(message)

@receiver(user_login_failed)
def log_login_failed(sender, credentials, request, **kwargs):
    ip = get_client_ip(request)
    ip_location = get_ip_location(ip)
    user_agent_info = get_user_agent_info(request.META.get('HTTP_USER_AGENT', ''))
    reverse_dns = get_reverse_dns(ip)
    email = credentials.get('email', 'None')
    message = (
        f"Failed login attempt: IP: {ip}, Reverse DNS: {reverse_dns}, "
        f"Location: {ip_location.get('city')}, {ip_location.get('region')}, {ip_location.get('country')}, "
        f"ISP: {ip_location.get('isp')}, OS: {user_agent_info['os']}, "
        f"App: {user_agent_info['application']}, Browser: {user_agent_info['browser']}, "
        f"Device: {user_agent_info['device']}, Email: {email}"
    )
    auth_logger.warning(message)

@receiver(user_logged_in)
def log_login_success(sender, request, user, **kwargs):
    ip = get_client_ip(request)
    ip_location = get_ip_location(ip)
    user_agent_info = get_user_agent_info(request.META.get('HTTP_USER_AGENT', ''))
    reverse_dns = get_reverse_dns(ip)
    message = (
        f"Successful login: IP: {ip}, Reverse DNS: {reverse_dns}, "
        f"Location: {ip_location.get('city')}, {ip_location.get('region')}, {ip_location.get('country')}, "
        f"ISP: {ip_location.get('isp')}, OS: {user_agent_info['os']}, "
        f"App: {user_agent_info['application']}, Browser: {user_agent_info['browser']}, "
        f"Device: {user_agent_info['device']}, Email: {user.email}"
    )
    auth_logger.info(message)
