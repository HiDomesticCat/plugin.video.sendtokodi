#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SendToKodi - Ultimate Fallback Strategy
Automatically tries ALL methods until one works - NO website list needed!

Strategy Waterfall:
1. Try direct play WITH headers (fastest & most reliable)
2. If fails → Try yt-dlp best
3. If fails → Try yt-dlp alternative format
4. If fails → Try yt-dlp worst quality (last resort)
5. Report failure only if ALL methods fail

NO HARDCODED WEBSITE LISTS - Works for ANY site automatically!
"""

import sys
import os
from urllib.parse import urlparse, unquote
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

__addon__ = xbmcaddon.Addon()
__handle__ = int(sys.argv[1])

DIRECT_MEDIA_EXTENSIONS = (
    '.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v',
    '.mpg', '.mpeg', '.3gp', '.ogv', '.ts', '.vob',
    '.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a', '.wma', '.opus',
    '.m3u8', '.mpd'
)


# ============================================================
# LOGGING
# ============================================================

def log(message):
    xbmc.log(f"plugin.video.sendtokodi: {message}", xbmc.LOGINFO)

def log_error(message):
    xbmc.log(f"plugin.video.sendtokodi ERROR: {message}", xbmc.LOGERROR)

def showInfoNotification(message):
    xbmcgui.Dialog().notification("SendToKodi", message, 
                                  xbmcgui.NOTIFICATION_INFO, 5000)

def showErrorNotification(message):
    xbmcgui.Dialog().notification("SendToKodi", message,
                                  xbmcgui.NOTIFICATION_ERROR, 5000)


# ============================================================
# URL UTILITIES
# ============================================================

def is_direct_media_url(url):
    """Check if URL is a direct media file"""
    try:
        url_base = url.split('|')[0] if '|' in url else url
        parsed = urlparse(url_base)
        path = unquote(parsed.path.lower())
        
        for ext in DIRECT_MEDIA_EXTENSIONS:
            if path.endswith(ext):
                return True
        
        if '?' in url_base:
            base_path = url_base.split('?')[0].lower()
            for ext in DIRECT_MEDIA_EXTENSIONS:
                if base_path.endswith(ext):
                    return True
        
        return False
    except:
        return False


def is_nextcloud_share_url(url):
    return '/s/' in url and '/download' not in url


def convert_nextcloud_to_direct(url):
    if is_nextcloud_share_url(url):
        return url.rstrip('/') + '/download'
    return url


def is_webdav_url(url):
    return url.startswith('webdav://') or url.startswith('webdavs://')


def convert_webdav_to_https(url):
    if url.startswith('webdav://'):
        return url.replace('webdav://', 'https://', 1)
    elif url.startswith('webdavs://'):
        return url.replace('webdavs://', 'https://', 1)
    return url


def get_universal_headers(url):
    """Generate complete browser headers"""
    url_base = url.split('|')[0] if '|' in url else url
    parsed = urlparse(url_base)
    domain = parsed.netloc.lower()
    scheme = parsed.scheme
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5',
        'Accept-Language': 'en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7,ja;q=0.6',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'video',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'same-origin',
        'DNT': '1',
        'Cache-Control': 'no-cache',
    }
    
    if domain:
        base_url = f"{scheme}://{domain}/"
        headers['Referer'] = base_url
        headers['Origin'] = base_url.rstrip('/')
    
    header_str = '&'.join([f'{k}={v}' for k, v in headers.items()])
    return header_str


# ============================================================
# LISTITEM CREATION
# ============================================================

def get_mime_type(url):
    """Get MIME type from URL"""
    url_lower = url.lower().split('|')[0]
    
    mime_map = {
        '.mp4': 'video/mp4', '.m4v': 'video/mp4',
        '.mkv': 'video/x-matroska', '.avi': 'video/x-msvideo',
        '.mov': 'video/quicktime', '.wmv': 'video/x-ms-wmv',
        '.webm': 'video/webm', '.flv': 'video/x-flv',
        '.m3u8': 'application/vnd.apple.mpegurl',
        '.mpd': 'application/dash+xml',
        '.mp3': 'audio/mpeg', '.flac': 'audio/flac',
    }
    
    for ext, mime in mime_map.items():
        if url_lower.endswith(ext):
            return mime
    return None


def create_listitem(url, with_headers=False, title=None):
    """Create ListItem with optional headers"""
    
    # Add headers if requested
    if with_headers and '|' not in url:
        headers = get_universal_headers(url)
        url_with_headers = f"{url}|{headers}"
    else:
        url_with_headers = url
    
    list_item = xbmcgui.ListItem(path=url_with_headers)
    list_item.setProperty('IsPlayable', 'true')
    list_item.setContentLookup(False)
    
    if title:
        list_item.setInfo('video', {'title': title})
    
    url_base = url.split('|')[0]
    url_lower = url_base.lower()
    
    # HLS
    if '.m3u8' in url_lower:
        list_item.setProperty('inputstream', 'inputstream.adaptive')
        list_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
        list_item.setMimeType('application/vnd.apple.mpegurl')
        list_item.setProperty('inputstream.adaptive.manifest_update_parameter', 'full')
    
    # DASH
    elif '.mpd' in url_lower:
        list_item.setProperty('inputstream', 'inputstream.adaptive')
        list_item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
        list_item.setMimeType('application/dash+xml')
    
    # Standard files
    else:
        mime_type = get_mime_type(url_base)
        if mime_type:
            list_item.setMimeType(mime_type)
        list_item.setProperty('seekable', 'true')
        list_item.setProperty('http-seekable', 'true')
    
    return list_item


# ============================================================
# YT-DLP INTEGRATION
# ============================================================

def get_ytdlp_module():
    """Import yt-dlp or youtube-do"""
    try:
        if sys.version_info[0] >= 3 and sys.version_info[1] >= 6:
            from lib.yt_dlp import YoutubeDL
            return YoutubeDL
        else:
            from lib.youtube_dl import YoutubeDL
            return YoutubeDL
    except ImportError:
        return None


def try_ytdlp(url, format_preference='best'):
    """
    Try to extract with yt-dlp
    Returns: ListItem or None
    """
    YoutubeDL = get_ytdlp_module()
    if not YoutubeDL:
        log("yt-dlp not available")
        return None
    
    try:
        log(f"Trying yt-dlp with format: {format_preference}")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
            'nocheckcertificate': True,
            'format': format_preference,
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=False)
            
            if not result:
                return None
            
            # Extract URL
            if 'url' in result:
                extracted_url = result['url']
            elif 'formats' in result and len(result['formats']) > 0:
                extracted_url = result['formats'][-1]['url']
            else:
                return None
            
            # Log what we got
            if '.m3u8' in extracted_url:
                log("✓ yt-dlp extracted m3u8!")
            elif '.mpd' in extracted_url:
                log("✓ yt-dlp extracted mpd!")
            else:
                log(f"yt-dlp extracted: {extracted_url[:50]}...")
            
            # Get title if available
            title = result.get('title', None)
            
            # Create ListItem - 強制加上 headers
            return create_listitem(extracted_url, with_headers=True, title=title)
    
    except Exception as e:
        log(f"yt-dlp failed: {e}")
        return None


# ============================================================
# ULTIMATE FALLBACK STRATEGY
# ============================================================

def process_url_with_fallback(url):
    """
    ULTIMATE FALLBACK STRATEGY - 優化版
    """
    
    # Clean URL
    url = convert_nextcloud_to_direct(url)
    url = convert_webdav_to_https(url)
    
    log("=" * 60)
    log(f"URL: {url[:100]}...")
    log("Starting optimized fallback waterfall...")
    
    # Check if direct media
    is_direct = is_direct_media_url(url)
    
    # ========================================
    # METHOD 1: Direct play WITH headers (最快、最可靠)
    # ========================================
    if is_direct:
        log("Method 1: Trying direct play WITH headers...")
        try:
            listitem = create_listitem(url, with_headers=True)
            log("✓ Method 1 SUCCESS: Direct with headers")
            showInfoNotification("Playing (direct + headers)")
            return listitem
        except Exception as e:
            log(f"✗ Method 1 failed: {e}")
    
    # ========================================
    # METHOD 2: yt-dlp best (會自動帶 headers)
    # ========================================
    log("Method 2: Trying yt-dlp best...")
    listitem = try_ytdlp(url, format_preference='best')
    if listitem:
        log("✓ Method 2 SUCCESS: yt-dlp best")
        showInfoNotification("Playing (yt-dlp best)")
        return listitem
    else:
        log("✗ Method 2 failed")
    
    # ========================================
    # METHOD 3: yt-dlp alternative format
    # ========================================
    log("Method 3: Trying yt-dlp alternative format...")
    listitem = try_ytdlp(url, format_preference='bestvideo+bestaudio/best')
    if listitem:
        log("✓ Method 3 SUCCESS: yt-dlp alternative")
        showInfoNotification("Playing (yt-dlp alt)")
        return listitem
    else:
        log("✗ Method 3 failed")
    
    # ========================================
    # METHOD 4: yt-dlp worst quality (last resort)
    # ========================================
    log("Method 4: Trying yt-dlp worst quality...")
    listitem = try_ytdlp(url, format_preference='worst')
    if listitem:
        log("✓ Method 4 SUCCESS: yt-dlp worst")
        showInfoNotification("Playing (low quality)")
        return listitem
    else:
        log("✗ Method 4 failed")
    
    # ========================================
    # ALL METHODS FAILED
    # ========================================
    log("✗✗✗ ALL METHODS FAILED ✗✗✗")
    log("=" * 60)
    return None


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    try:
        log("=" * 60)
        log("SendToKodi - Ultimate Fallback (Optimized)")
        log("=" * 60)
        
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
        
        # Try all methods
        listitem = process_url_with_fallback(url)
        
        if listitem:
            log("SUCCESS - Starting playback")
            xbmcplugin.setResolvedUrl(__handle__, True, listitem=listitem)
        else:
            log_error("FAILURE - All methods exhausted")
            showErrorNotification("Unable to play - all methods failed")
            xbmcplugin.setResolvedUrl(__handle__, False, xbmcgui.ListItem())
        
        log("=" * 60)
        
    except Exception as e:
        log_error(f"Fatal error: {e}")
        import traceback
        log_error(traceback.format_exc())
        showErrorNotification(f"Error: {str(e)}")
        xbmcplugin.setResolvedUrl(__handle__, False, xbmcgui.ListItem())