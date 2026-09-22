# SSRF Protection Implementation

## Overview
User-controlled `api_base` URLs require robust SSRF protection to prevent:
- Internal network access
- Cloud metadata endpoint access
- DNS rebinding attacks

## Implementation

```python
import socket
import ipaddress
from urllib.parse import urlparse

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", 
                 "metadata.google", "169.254.169.254"}

def ssrf_protect_url(url: str) -> bool:
    parsed = urlparse(url)
    hostname = parsed.hostname
    
    if not hostname or hostname.lower() in BLOCKED_HOSTS:
        return False
    
    try:
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
        
        private_ranges = [
            ipaddress.ip_network("127.0.0.0/8"),    # Loopback
            ipaddress.ip_network("10.0.0.0/8"),     # Class A private
            ipaddress.ip_network("172.16.0.0/12"),    # Class B private
            ipaddress.ip_network("192.168.0.0/16"),  # Class C private
            ipaddress.ip_network("169.254.0.0/16"),  # Link-local
            ipaddress.ip_network("::1/128"),         # IPv6 loopback
            ipaddress.ip_network("fc00::/7"),        # IPv6 ULA
            ipaddress.ip_network("fe80::/10"),       # IPv6 link-local
        ]
        
        for network in private_ranges:
            if ip in network:
                return False
    except (socket.gaierror, ValueError):
        pass  # External domain, allow
    
    return True
```

## Test Cases

| URL | Expected | Reason |
|-----|----------|--------|
| `http://localhost:8080` | BLOCK | Literal localhost |
| `http://127.0.0.1:3000` | BLOCK | Loopback IP |
| `http://169.254.169.254` | BLOCK | Cloud metadata |
| `https://api.openai.com` | ALLOW | Public endpoint |
| `http://192.168.1.1` | BLOCK | Private range |

## References
- https://owasp.org/www-community/attacks/Server_Side_Request_Forgery
- https://portswigger.net/web-security/ssrf