"""Paths, constants, and feed configuration."""

from pathlib import Path

DATA_DIR = Path("./data")

# MaxMind
MAXMIND_DOWNLOAD_URL = "https://download.maxmind.com/geoip/databases/GeoLite2-City/download?suffix=tar.gz"
MAXMIND_DIR = DATA_DIR / "maxmind"
MAXMIND_DB_FILE = MAXMIND_DIR / "GeoLite2-City.mmdb"

# IPinfo
IPINFO_DOWNLOAD_URL = "https://ipinfo.io/data/ipinfo_lite.mmdb"
IPINFO_DIR = DATA_DIR / "ipinfo"
IPINFO_DB_FILE = IPINFO_DIR / "ipinfo_lite.mmdb"

# IP2Location
IP2LOCATION_DOWNLOAD_URL_V6 = "https://www.ip2location.com/download/"
IP2LOCATION_DIR = DATA_DIR / "ip2location"
IP2LOCATION_DB_FILE = IP2LOCATION_DIR / "IP2LOCATION-LITE-DB3.IPV6.BIN"

# Assets
ASSETS_DIR = DATA_DIR / "assets"
AWS_LOGO_FILE = ASSETS_DIR / "aws-logo.svg"
AWS_LOGO_URL = "https://docs.aws.amazon.com/assets/r/images/aws_logo_dark.svg"
AWS_CARD_LOGO_FILE = ASSETS_DIR / "aws-card-logo.svg"
AWS_CARD_LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/9/93/Amazon_Web_Services_Logo.svg"
AS213151_LOGO_FILE = ASSETS_DIR / "as213151-logo.png"
AS213151_LOGO_URL = "https://as213151.net/images/AS213151.png"
STARLINK_LOGO_FILE = ASSETS_DIR / "starlink-logo.svg"
STARLINK_LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/a/a8/Starlink_Logo.svg"

MAXMIND_FAVICON_FILE = ASSETS_DIR / "maxmind-favicon.ico"
MAXMIND_FAVICON_URL = "https://www.maxmind.com/favicon.ico"
IPINFO_FAVICON_FILE = ASSETS_DIR / "ipinfo-favicon.ico"
IPINFO_FAVICON_URL = "https://ipinfo.io/favicon.ico"
IP2LOCATION_FAVICON_FILE = ASSETS_DIR / "ip2location-favicon.ico"
IP2LOCATION_FAVICON_URL = "https://www.ip2location.com/favicon.ico"

GOOGLE_CLOUD_ICON_FILE = ASSETS_DIR / "google-cloud-icon.svg"
MICROSOFT_LOGO_FILE = ASSETS_DIR / "microsoft-logo.svg"
MICROSOFT_LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg"

GLOBE_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>'
GLOBE_FAVICON = 'data:image/svg+xml,' + '<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22><rect width=%2224%22 height=%2224%22 rx=%224%22 fill=%22%23232f3e%22/><circle cx=%2212%22 cy=%2212%22 r=%228%22 fill=%22none%22 stroke=%22white%22 stroke-width=%221.2%22/><path d=%22M4 12h16%22 fill=%22none%22 stroke=%22white%22 stroke-width=%221.2%22/><path d=%22M12 4a12 12 0 0 1 3.2 8 12 12 0 0 1-3.2 8 12 12 0 0 1-3.2-8A12 12 0 0 1 12 4z%22 fill=%22none%22 stroke=%22white%22 stroke-width=%221.2%22/></svg>'

FEEDS = [
    {
        "url": "https://ip-ranges.amazonaws.com/geo-ip-feed.csv",
        "output": Path("./aws.html"),
        "title": "AWS Geofeed Monitoring Report (Official)",
        "topbar_title": "AWS Geofeed Monitoring Report (Official)",
        "logo_file": AWS_LOGO_FILE,
        "logo_type": "svg",
        "card_logo_file": AWS_CARD_LOGO_FILE,
        "card_logo_type": "svg",
    },
    {
        "url": "https://www.gstatic.com/ipranges/cloud_geofeed",
        "output": Path("./gcp.html"),
        "title": "Google Cloud Geofeed Monitoring Report",
        "topbar_title": "Google Cloud Geofeed Monitoring Report",
        "logo_file": GOOGLE_CLOUD_ICON_FILE,
        "logo_type": "svg",
        "card_logo_file": GOOGLE_CLOUD_ICON_FILE,
        "card_logo_type": "svg",
    },
    {
        "url": "https://www.microsoft.com/en-us/download/details.aspx?id=53601",
        "output": Path("./microsoft.html"),
        "title": "Microsoft Geofeed Monitoring Report",
        "topbar_title": "Microsoft Geofeed Monitoring Report",
        "logo_file": MICROSOFT_LOGO_FILE,
        "logo_type": "svg",
        "logo_invert": False,
        "card_logo_file": MICROSOFT_LOGO_FILE,
        "card_logo_type": "svg",
        "geofeed_format": "microsoft",
    },
    {
        "url": "https://raw.githubusercontent.com/chriselsen/AWS-Geofeed/main/data/aws-geofeed.txt",
        "output": Path("./aws-ce.html"),
        "title": "AWS Geofeed Monitoring Report (Christian Elsen)",
        "topbar_title": "AWS Geofeed Monitoring Report (Christian Elsen)",
        "logo_file": AWS_LOGO_FILE,
        "logo_type": "svg",
        "card_logo_file": AWS_CARD_LOGO_FILE,
        "card_logo_type": "svg",
    },
    {
        "url": "https://raw.githubusercontent.com/AS213151/rfc8805-geofeed/main/as213151-geo-ip.txt",
        "output": Path("./as213151.html"),
        "title": "AS213151 Geofeed Monitoring Report",
        "topbar_title": "AS213151 Geofeed Monitoring Report",
        "logo_file": AS213151_LOGO_FILE,
        "logo_type": "png",
        "logo_invert": True,
        "card_logo_file": AS213151_LOGO_FILE,
        "card_logo_type": "png",
    },
    {
        "url": "https://geoip.starlinkisp.net/",
        "output": Path("./starlink.html"),
        "title": "Starlink Geofeed Monitoring Report",
        "topbar_title": "Starlink Geofeed Monitoring Report",
        "logo_file": STARLINK_LOGO_FILE,
        "logo_type": "svg",
        "logo_invert": True,
        "card_logo_file": STARLINK_LOGO_FILE,
        "card_logo_type": "svg",
    },
]
