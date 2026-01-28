#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SendToKodi - Enhanced Service
Plays various stream sites on Kodi using yt-dlp with direct media support

Features:
- Direct media file support (mp4, mkv, avi, etc.)
- Automatic Nextcloud share URL conversion
- WebDAV protocol support
- Improved seeking/fast-forward support
- HLS and DASH manifest support
- Fallback to yt-dlp for complex URLs
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
    # Video formats
    '.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v',
    '.mpg', '.mpeg', '.3gp', '.ogv', '.ts', '.vob',
    # Audio formats
    '.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a', '.wma', '.opus',
    # Streaming formats
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
    """
    Detect if URL is a direct media file
    
    Args:
        url: URL string to check
    
    Returns:
        bool: True if URL points to a playable media file
    """
    try:
        parsed = urlparse(url)
        path = unquote(parsed.path.lower())
        
        # Check file extension in path
        for ext in DIRECT_MEDIA_EXTENSIONS:
            if path.endswith(ext):
                log(f"Detected direct media file: {ext}")
                return True
        
        # Check file extension before query parameters
        if '?' in url:
            base_path = url.split('?')[0].lower()
            for ext in DIRECT_MEDIA_EXTENSIONS:
                if base_path.endswith(ext):
                    log(f"Detected direct media file in URL: {ext}")
                    return True
        
        return False
    except Exception as e:
        log_error(f"Error checking direct media URL: {e}")
        return False


def is_nextcloud_share_url(url):
    """
    Detect Nextcloud share URLs
    
    Args:
        url: URL string to check
    
    Returns:
        bool: True if URL is a Nextcloud share link
    """
    return '/s/' in url and '/download' not in url and '/preview' not in url


def is_webdav_url(url):
    """
    Detect WebDAV URLs
    
    Args:
        url: URL string to check
    
    Returns:
        bool: True if URL uses WebDAV protocol
    """
    return url.startswith('webdav://') or url.startswith('webdavs://')


def convert_nextcloud_to_direct(url):
    """
    Convert Nextcloud share URL to direct download URL
    
    Args:
        url: Nextcloud share URL
    
    Returns:
        str: Direct download URL
    
    Example:
        Input:  https://cloud.example.com/s/ABC123
        Output: https://cloud.example.com/s/ABC123/download
    """
    if is_nextcloud_share_url(url):
        direct_url = url.rstrip('/') + '/download'
        log(f"Converted Nextcloud URL to direct download")
        return direct_url
    return url


def convert_webdav_to_https(url):
    """
    Convert WebDAV URL to HTTPS URL for better compatibility
    
    Args:
        url: WebDAV URL
    
    Returns:
        str: HTTPS URL
    
    Example:
        Input:  webdav://user:pass@host/path
        Output: https://user:pass@host/path
    """
    if url.startswith('webdav://'):
        https_url = url.replace('webdav://', 'https://', 1)
        log("Converted WebDAV to HTTPS")
        return https_url
    elif url.startswith('webdavs://'):
        https_url = url.replace('webdavs://', 'https://', 1)
        log("Converted WebDAVS to HTTPS")
        return https_url
    return url


def sanitize_url(url):
    """
    Clean and prepare URL for playback
    
    Args:
        url: Raw URL string
    
    Returns:
        str: Sanitized URL
    """
    # Remove leading/trailing whitespace
    url = url.strip()
    
    # Auto-convert Nextcloud share URLs
    url = convert_nextcloud_to_direct(url)
    
    # Convert WebDAV to HTTPS
    url = convert_webdav_to_https(url)
    
    return url


# ============================================================
# LISTITEM CREATION
# ============================================================

def get_mime_type(url):
    """
    Determine MIME type from URL
    
    Args:
        url: URL string
    
    Returns:
        str: MIME type or None
    """
    url_lower = url.lower()
    
    # Video MIME types
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
        # Audio MIME types
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
    Create ListItem for direct media URL with full seeking support
    
    Args:
        url: Direct media URL
    
    Returns:
        xbmcgui.ListItem: Configured ListItem for playback
    """
    log(f"Creating direct media ListItem")
    
    # Create ListItem with URL as path
    list_item = xbmcgui.ListItem(path=url)
    list_item.setProperty('IsPlayable', 'true')
    
    # Disable content lookup for direct URLs (improves performance)
    list_item.setContentLookup(False)
    
    url_lower = url.lower()
    
    # ===== HLS Streaming (.m3u8) =====
    if url_lower.endswith('.m3u8') or 'master.m3u8' in url_lower or 'playlist.m3u8' in url_lower:
        log("Configuring for HLS stream")
        list_item.setProperty('inputstream', 'inputstream.adaptive')
        list_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
        
        # Set MIME type
        mime_type = 'application/vnd.apple.mpegurl'
        list_item.setMimeType(mime_type)
        
        # Enable seeking for HLS if possible
        list_item.setProperty('inputstream.adaptive.manifest_update_parameter', 'full')
        log(f"HLS stream configured with MIME type: {mime_type}")
    
    # ===== DASH Streaming (.mpd) =====
    elif url_lower.endswith('.mpd') or 'manifest.mpd' in url_lower:
        log("Configuring for DASH stream")
        list_item.setProperty('inputstream', 'inputstream.adaptive')
        list_item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
        
        # Set MIME type
        mime_type = 'application/dash+xml'
        list_item.setMimeType(mime_type)
        log(f"DASH stream configured with MIME type: {mime_type}")
    
    # ===== Standard Media Files =====
    else:
        # Get and set MIME type
        mime_type = get_mime_type(url)
        if mime_type:
            list_item.setMimeType(mime_type)
            log(f"Set MIME type: {mime_type}")
        
        # CRITICAL: Enable seeking for standard media files
        # This tells Kodi to use HTTP range requests
        list_item.setProperty('seekable', 'true')
        
        # Additional property for HTTP seeking
        list_item.setProperty('http-seekable', 'true')
        
        log("Enabled seeking properties for standard media file")
    
    return list_item


# ============================================================
# YT-DLP INTEGRATION
# ============================================================

def get_ytdlp_module():
    """
    Import and return yt-dlp or youtube-dl module
    
    Returns:
        module: YoutubeDL class or None
    """
    try:
        # Try yt-dlp first (Python 3.6+)
        if sys.version_info[0] >= 3 and sys.version_info[1] >= 6:
            from lib.yt_dlp import YoutubeDL
            log("Using yt-dlp resolver")
            return YoutubeDL
        else:
            # Fallback to youtube-dl for older Python
            from lib.youtube_dl import YoutubeDL
            log("Using youtube-dl resolver (legacy)")
            return YoutubeDL
    except ImportError as e:
        log_error(f"Failed to import resolver: {e}")
        return None


def get_ytdlp_options():
    """
    Get yt-dlp extraction options
    
    Returns:
        dict: yt-dlp options
    """
    return {
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': False,
        'nocheckcertificate': True,
        'format': 'best',
    }


def extract_with_ytdlp(url):
    """
    Extract video information using yt-dlp
    
    Args:
        url: URL to extract
    
    Returns:
        dict: Video information or None
    """
    YoutubeDL = get_ytdlp_module()
    if not YoutubeDL:
        log_error("No resolver available (yt-dlp or youtube-dl)")
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
    """
    Create ListItem from yt-dlp extraction result
    
    Args:
        result: yt-dlp extraction result dict
    
    Returns:
        xbmcgui.ListItem: Configured ListItem or None
    """
    try:
        # Check if result has formats
        if 'formats' not in result and 'url' not in result:
            log_error("No playable formats found in yt-dlp result")
            return None
        
        # Get best format URL
        if 'url' in result:
            url = result['url']
        elif 'formats' in result and len(result['formats']) > 0:
            # Get the last format (usually best quality)
            url = result['formats'][-1]['url']
        else:
            log_error("Could not find URL in yt-dlp result")
            return None
        
        log(f"Creating ListItem from yt-dlp result")
        
        # Create ListItem
        list_item = xbmcgui.ListItem(path=url)
        list_item.setProperty('IsPlayable', 'true')
        
        # Add metadata if available
        if 'title' in result:
            list_item.setInfo('video', {'title': result['title']})
        
        # Check if we need inputstream.adaptive for manifest
        if url.endswith('.m3u8'):
            list_item.setProperty('inputstream', 'inputstream.adaptive')
            list_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
        elif url.endswith('.mpd'):
            list_item.setProperty('inputstream', 'inputstream.adaptive')
            list_item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
        
        return list_item
        
    except Exception as e:
        log_error(f"Error creating ListItem from yt-dlp result: {e}")
        return None


# ============================================================
# MAIN PROCESSING
# ============================================================

def process_url(url):
    """
    Main URL processing function
    
    Args:
        url: URL to process
    
    Returns:
        xbmcgui.ListItem: ListItem ready for playback or None
    """
    # Sanitize URL
    url = sanitize_url(url)
    log(f"Processing URL: {url}")
    
    # Check if this is a direct media file
    if is_direct_media_url(url):
        log("Direct media URL detected - bypassing yt-dlp")
        
        try:
            listitem = create_direct_media_listitem(url)
            showInfoNotification("Playing direct media")
            return listitem
            
        except Exception as e:
            log_error(f"Error creating direct media ListItem: {e}")
            showErrorNotification("Failed to play direct media")
            return None
    
    # Not a direct media file - use yt-dlp
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
        log("SendToKodi service started")
        
        # Get URL from plugin arguments
        if len(sys.argv) < 3:
            log_error("No URL provided")
            showErrorNotification("No URL provided")
            xbmcplugin.setResolvedUrl(__handle__, False, xbmcgui.ListItem())
            sys.exit(1)
        
        # Extract URL (remove leading '?')
        url = sys.argv[2][1:] if sys.argv[2].startswith('?') else sys.argv[2]
        
        if not url:
            log_error("Empty URL")
            showErrorNotification("Empty URL")
            xbmcplugin.setResolvedUrl(__handle__, False, xbmcgui.ListItem())
            sys.exit(1)
        
        log(f"Received URL: {url[:100]}...")  # Log first 100 chars
        
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