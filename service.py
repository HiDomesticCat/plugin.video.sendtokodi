#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SendToKodi - Universal Anti-Hotlink Protection
Uses complete browser headers for ALL sites - no need for site-specific code!

Strategy: Simulate a real browser request for EVERY URL
This works for most anti-hotlink protection systems
"""

import sys
import os
import re
from urllib.parse import urlparse, unquote, parse_qs
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

# Get addon settings
__addon__ = xbmcaddon.Addon()
__handle__ = int(sys.argv[1])

# Supported direct media file extensions
DIRECT_MEDIA_EXTENSIONS = (
    '.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v',
    '.mpg', '.mpeg', '.3gp', '.ogv', '.ts', '.vob',
    '.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a', '.wma', '.opus',
    '.m3u8', '.mpd'
)


# ============================================================
# LOGGING AND NOTIFICATIONS
# ============================================================

def log(message):
    """Log message to Kodi log with plugin prefix"""
    xbmc.log(f"plugin.video.sendtokodi: {message}", xbmc.LOGINFO)


def log_error(message):
    """Log error message to Kodi log"""
    xbmc.log(f"plugin.video.sendtokodi ERROR: {message}", xbmc.LOGERROR)


def showInfoNotification(message):
    """Show info notification to user"""
    xbmcgui.Dialog().notification("SendToKodi", message, 
                                  xbmcgui.NOTIFICATION_INFO, 5000)


def showErrorNotification(message):
    """Show error notification to user"""
    xbmcgui.Dialog().notification("SendToKodi", message,
                                  xbmcgui.NOTIFICATION_ERROR, 5000)


# ============================================================
# URL DETECTION AND CONVERSION
# ============================================================

def is_direct_media_url(url):
    """Detect if URL is a direct media file"""
    try:
        url_base = url.split('|')[0] if '|' in url else url
        parsed = urlparse(url_base)
        path = unquote(parsed.path.lower())
        
        for ext in DIRECT_MEDIA_EXTENSIONS:
            if path.endswith(ext):
                log(f"Detected direct media file: {ext}")
                return True
        
        if '?' in url_base:
            base_path = url_base.split('?')[0].lower()
            for ext in DIRECT_MEDIA_EXTENSIONS:
                if base_path.endswith(ext):
                    log(f"Detected direct media file in URL: {ext}")
                    return True
        
        return False
    except Exception as e:
        log_error(f"Error checking direct media URL: {e}")
        return False


def is_nextcloud_share_url(url):
    """Detect Nextcloud share URLs"""
    return '/s/' in url and '/download' not in url and '/preview' not in url


def is_webdav_url(url):
    """Detect WebDAV URLs"""
    return url.startswith('webdav://') or url.startswith('webdavs://')


def convert_nextcloud_to_direct(url):
    """Convert Nextcloud share URL to direct download URL"""
    if is_nextcloud_share_url(url):
        direct_url = url.rstrip('/') + '/download'
        log(f"Converted Nextcloud URL to direct download")
        return direct_url
    return url


def convert_webdav_to_https(url):
    """Convert WebDAV URL to HTTPS URL"""
    if url.startswith('webdav://'):
        https_url = url.replace('webdav://', 'https://', 1)
        log("Converted WebDAV to HTTPS")
        return https_url
    elif url.startswith('webdavs://'):
        https_url = url.replace('webdavs://', 'https://', 1)
        log("Converted WebDAVS to HTTPS")
        return https_url
    return url


def get_universal_headers(url):
    """
    UNIVERSAL ANTI-HOTLINK SOLUTION
    
    Generate complete browser headers for ANY URL
    This simulates a real browser request and works for most anti-hotlink systems
    
    No need to add site-specific code anymore!
    """
    url_base = url.split('|')[0] if '|' in url else url
    parsed = urlparse(url_base)
    domain = parsed.netloc.lower()
    scheme = parsed.scheme
    
    # Complete browser headers - works for most sites
    headers = {
        # Browser identification
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        
        # Content negotiation
        'Accept': 'video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5',
        'Accept-Language': 'en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7,ja;q=0.6',
        'Accept-Encoding': 'gzip, deflate, br',
        
        # Connection management
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        
        # Security context (modern browsers)
        'Sec-Fetch-Dest': 'video',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'same-origin',
        
        # DNT (Do Not Track)
        'DNT': '1',
        
        # Cache control
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    }
    
    # Add Referer and Origin for anti-hotlink protection
    # Use the same domain as the video URL - this is the KEY!
    if domain:
        base_url = f"{scheme}://{domain}/"
        headers['Referer'] = base_url
        headers['Origin'] = base_url.rstrip('/')
        log(f"Using universal headers with Referer: {base_url}")
    
    # Format headers for Kodi URL format: url|Header1=value1&Header2=value2
    header_str = '&'.join([f'{k}={v}' for k, v in headers.items()])
    
    return header_str


def sanitize_url(url):
    """Clean and prepare URL for playback"""
    url = url.strip()
    url = convert_nextcloud_to_direct(url)
    url = convert_webdav_to_https(url)
    return url


# ============================================================
# LISTITEM CREATION
# ============================================================

def get_mime_type(url):
    """Determine MIME type from URL"""
    url_lower = url.lower().split('|')[0]
    
    mime_map = {
        '.mp4': 'video/mp4',
        '.m4v': 'video/mp4',
        '.mkv': 'video/x-matroska',
        '.avi': 'video/x-msvideo',
        '.mov': 'video/quicktime',
        '.wmv': 'video/x-ms-wmv',
        '.flv': 'video/x-flv',
        '.webm': 'video/webm',
        '.mpg': 'video/mpeg',
        '.mpeg': 'video/mpeg',
        '.m3u8': 'application/vnd.apple.mpegurl',
        '.mpd': 'application/dash+xml',
        '.mp3': 'audio/mpeg',
        '.flac': 'audio/flac',
        '.wav': 'audio/wav',
        '.aac': 'audio/aac',
        '.m4a': 'audio/mp4',
        '.ogg': 'audio/ogg',
        '.opus': 'audio/opus',
    }
    
    for ext, mime in mime_map.items():
        if url_lower.endswith(ext):
            return mime
    
    return None


def create_direct_media_listitem(url):
    """
    Create ListItem for direct media URL with UNIVERSAL anti-hotlink protection
    
    This now works for ALL websites automatically!
    """
    log(f"Creating direct media ListItem with universal headers")
    
    # Add universal browser headers (works for all sites!)
    if '|' not in url:
        headers = get_universal_headers(url)
        url_with_headers = f"{url}|{headers}"
        log("Applied universal anti-hotlink headers")
    else:
        url_with_headers = url
        log("URL already contains headers")
    
    # Create ListItem
    list_item = xbmcgui.ListItem(path=url_with_headers)
    list_item.setProperty('IsPlayable', 'true')
    list_item.setContentLookup(False)
    
    # Get base URL for format detection
    url_base = url.split('|')[0]
    url_lower = url_base.lower()
    
    # HLS Streaming
    if url_lower.endswith('.m3u8') or 'master.m3u8' in url_lower or 'playlist.m3u8' in url_lower:
        log("Configuring for HLS stream")
        list_item.setProperty('inputstream', 'inputstream.adaptive')
        list_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
        list_item.setMimeType('application/vnd.apple.mpegurl')
        list_item.setProperty('inputstream.adaptive.manifest_update_parameter', 'full')
    
    # DASH Streaming
    elif url_lower.endswith('.mpd') or 'manifest.mpd' in url_lower:
        log("Configuring for DASH stream")
        list_item.setProperty('inputstream', 'inputstream.adaptive')
        list_item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
        list_item.setMimeType('application/dash+xml')
    
    # Standard Media Files
    else:
        mime_type = get_mime_type(url_base)
        if mime_type:
            list_item.setMimeType(mime_type)
            log(f"Set MIME type: {mime_type}")
        
        # Enable seeking
        list_item.setProperty('seekable', 'true')
        list_item.setProperty('http-seekable', 'true')
        log("Enabled seeking properties")
    
    return list_item


# ============================================================
# YT-DLP INTEGRATION
# ============================================================

def get_ytdlp_module():
    """Import and return yt-dlp or youtube-dl module"""
    try:
        if sys.version_info[0] >= 3 and sys.version_info[1] >= 6:
            from lib.yt_dlp import YoutubeDL
            log("Using yt-dlp resolver")
            return YoutubeDL
        else:
            from lib.youtube_dl import YoutubeDL
            log("Using youtube-dl resolver (legacy)")
            return YoutubeDL
    except ImportError as e:
        log_error(f"Failed to import resolver: {e}")
        return None


def get_ytdlp_options():
    """Get yt-dlp extraction options"""
    return {
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': False,
        'nocheckcertificate': True,
        'format': 'best',
    }


def extract_with_ytdlp(url):
    """Extract video information using yt-dlp"""
    YoutubeDL = get_ytdlp_module()
    if not YoutubeDL:
        log_error("No resolver available")
        return None
    
    try:
        log(f"Extracting URL with yt-dlp")
        ydl_opts = get_ytdlp_options()
        
        with YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=False)
            
            if result:
                log("Successfully extracted video information")
                return result
            else:
                log_error("yt-dlp returned empty result")
                return None
                
    except Exception as e:
        log_error(f"yt-dlp extraction failed: {e}")
        return None


def create_listitem_from_ytdlp(result):
    """Create ListItem from yt-dlp extraction result"""
    try:
        if 'formats' not in result and 'url' not in result:
            log_error("No playable formats found")
            return None
        
        if 'url' in result:
            url = result['url']
        elif 'formats' in result and len(result['formats']) > 0:
            url = result['formats'][-1]['url']
        else:
            log_error("Could not find URL in result")
            return None
        
        log(f"Creating ListItem from yt-dlp result")
        
        list_item = xbmcgui.ListItem(path=url)
        list_item.setProperty('IsPlayable', 'true')
        
        if 'title' in result:
            list_item.setInfo('video', {'title': result['title']})
        
        if url.endswith('.m3u8'):
            list_item.setProperty('inputstream', 'inputstream.adaptive')
            list_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
        elif url.endswith('.mpd'):
            list_item.setProperty('inputstream', 'inputstream.adaptive')
            list_item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
        
        return list_item
        
    except Exception as e:
        log_error(f"Error creating ListItem: {e}")
        return None


# ============================================================
# MAIN PROCESSING
# ============================================================

def process_url(url):
    """Main URL processing function"""
    url = sanitize_url(url)
    log(f"Processing URL: {url[:100]}...")
    
    # Check if direct media file
    if is_direct_media_url(url):
        log("Direct media URL - using universal anti-hotlink protection")
        
        try:
            listitem = create_direct_media_listitem(url)
            showInfoNotification("Playing direct media")
            return listitem
            
        except Exception as e:
            log_error(f"Error creating direct media ListItem: {e}")
            showErrorNotification("Failed to play direct media")
            return None
    
    # Use yt-dlp for complex URLs
    else:
        log("Using yt-dlp to resolve URL")
        
        try:
            result = extract_with_ytdlp(url)
            
            if result:
                listitem = create_listitem_from_ytdlp(result)
                
                if listitem:
                    showInfoNotification("Playing stream")
                    return listitem
                else:
                    log_error("Failed to create ListItem from yt-dlp result")
                    showErrorNotification("Failed to create playback item")
                    return None
            else:
                log_error("yt-dlp failed to extract URL")
                showErrorNotification("Failed to resolve URL")
                return None
                
        except Exception as e:
            log_error(f"Error processing with yt-dlp: {e}")
            showErrorNotification(f"Error: {str(e)}")
            return None


# ============================================================
# PLUGIN ENTRY POINT
# ============================================================

if __name__ == '__main__':
    try:
        log("=" * 60)
        log("SendToKodi service started (Universal Anti-Hotlink)")
        
        if len(sys.argv) < 3:
            log_error("No URL provided")
            showErrorNotification("No URL provided")
            xbmcplugin.setResolvedUrl(__handle__, False, xbmcgui.ListItem())
            sys.exit(1)
        
        url = sys.argv[2][1:] if sys.argv[2].startswith('?') else sys.argv[2]
        
        if not url:
            log_error("Empty URL")
            showErrorNotification("Empty URL")
            xbmcplugin.setResolvedUrl(__handle__, False, xbmcgui.ListItem())
            sys.exit(1)
        
        log(f"Received URL: {url[:100]}...")
        
        # Process the URL
        listitem = process_url(url)
        
        # Resolve for playback
        if listitem:
            log("Successfully created ListItem - starting playback")
            xbmcplugin.setResolvedUrl(__handle__, True, listitem=listitem)
            log("Playback started successfully")
        else:
            log_error("Failed to create ListItem")
            xbmcplugin.setResolvedUrl(__handle__, False, xbmcgui.ListItem())
        
        log("SendToKodi service finished")
        log("=" * 60)
        
    except Exception as e:
        log_error(f"Fatal error in main: {e}")
        import traceback
        log_error(traceback.format_exc())
        showErrorNotification(f"Fatal error: {str(e)}")
        xbmcplugin.setResolvedUrl(__handle__, False, xbmcgui.ListItem())