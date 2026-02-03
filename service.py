#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SendToKodi - yt-dlp First Universal Strategy
所有連結強制先用 yt-dlp 提取（最高相容性，處理熱連結保護）
Only fallback to direct if yt-dlp completely fails
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

# 加入 addon 資源路徑，讓 import yt_dlp 更容易成功
addon_path = xbmcaddon.Addon().getAddonInfo('path')
lib_path = os.path.join(addon_path, 'lib')
sys.path.insert(0, lib_path)

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
    xbmcgui.Dialog().notification("SendToKodi", message, xbmcgui.NOTIFICATION_INFO, 5000)

def showErrorNotification(message):
    xbmcgui.Dialog().notification("SendToKodi", message, xbmcgui.NOTIFICATION_ERROR, 5000)

# ============================================================
# URL UTILITIES (保持原樣)
# ============================================================
def is_direct_media_url(url):
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
    url_base = url.split('|')[0] if '|' in url else url
    parsed = urlparse(url_base)
    domain = parsed.netloc.lower()
    scheme = parsed.scheme
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
        'Referer': f"{scheme}://{domain}/" if domain else '',
    }
    header_str = '&'.join([f'{k}={v}' for k, v in headers.items()])
    return header_str

# ============================================================
# LISTITEM CREATION (簡化)
# ============================================================
def get_mime_type(url):
    url_lower = url.lower().split('|')[0]
    mime_map = {
        '.mp4': 'video/mp4', '.m4v': 'video/mp4',
        '.mkv': 'video/x-matroska', '.avi': 'video/x-msvideo',
        '.mov': 'video/quicktime', '.wmv': 'video/x-ms-wmv',
        '.webm': 'video/webm', '.flv': 'video/x-flv',
        '.m3u8': 'application/vnd.apple.mpegurl',
        '.mpd': 'application/dash+xml',
    }
    for ext, mime in mime_map.items():
        if url_lower.endswith(ext):
            return mime
    return 'video/mp4'  # default fallback

def create_listitem(url, with_headers=False, title=None):
    if with_headers and '|' not in url:
        headers = get_universal_headers(url)
        url = f"{url}|{headers}"
    
    list_item = xbmcgui.ListItem(path=url)
    list_item.setProperty('IsPlayable', 'true')
    list_item.setContentLookup(False)
    
    if title:
        list_item.setInfo('video', {'title': title})
    
    url_lower = url.lower().split('|')[0]
    if '.m3u8' in url_lower:
        list_item.setProperty('inputstream', 'inputstream.adaptive')
        list_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
        list_item.setMimeType('application/vnd.apple.mpegurl')
    elif '.mpd' in url_lower:
        list_item.setProperty('inputstream', 'inputstream.adaptive')
        list_item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
        list_item.setMimeType('application/dash+xml')
    else:
        list_item.setMimeType(get_mime_type(url))
    
    return list_item

# ============================================================
# YT-DLP INTEGRATION
# ============================================================
def get_ytdlp_module():
    try:
        from yt_dlp import YoutubeDL
        log("yt-dlp import SUCCESS! Version loaded.")
        return YoutubeDL
    except ImportError as e:
        log_error(f"yt-dlp import FAILED: {str(e)} - Check resources/lib/yt_dlp folder")
        return None

def try_ytdlp(url, format_preference='best'):
    YoutubeDL = get_ytdlp_module()
    if not YoutubeDL:
        return None
    
    try:
        log(f"Trying yt-dlp ({format_preference}) on {url[:80]}...")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,  # 更寬鬆，避免小錯就停
            'nocheckcertificate': True,
            'format': format_preference,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
                'Referer': 'https://anime1.me/' if 'anime1.me' in url else '',
                'Accept': '*/*',
            },
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=False)
            
            if not result or not result.get('url') and not result.get('formats'):
                log("yt-dlp returned no usable info")
                return None
            
            extracted_url = result.get('url') or result['formats'][-1]['url']
            log(f"✓ yt-dlp extracted URL: {extracted_url[:80]}...")
            
            title = result.get('title', 'yt-dlp extracted')
            return create_listitem(extracted_url, with_headers=True, title=title)
    
    except Exception as e:
        log(f"yt-dlp failed: {str(e)}")
        return None

# ============================================================
# UNIVERSAL YT-DLP FIRST
# ============================================================
def process_url_with_fallback(url):
    url = convert_nextcloud_to_direct(url)
    url = convert_webdav_to_https(url)
    
    log("=" * 80)
    log(f"Processing URL: {url}")
    log("Strategy: yt-dlp FIRST (universal)")
    
    # 強制 yt-dlp 優先
    for fmt in ['best', 'bestvideo+bestaudio/best', 'worst']:
        log(f"Attempt {fmt}...")
        listitem = try_ytdlp(url, fmt)
        if listitem:
            showInfoNotification(f"Playing via yt-dlp ({fmt})")
            return listitem
    
    # 最後 fallback direct (極少用)
    if is_direct_media_url(url):
        log("yt-dlp failed - fallback direct + headers")
        try:
            listitem = create_listitem(url, with_headers=True)
            showInfoNotification("Playing direct fallback")
            return listitem
        except Exception as e:
            log(f"Direct fallback failed: {e}")
    
    log("ALL FAILED - cannot play")
    return None

# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    try:
        log("=" * 80)
        log("SendToKodi - yt-dlp Universal Mode")
        
        if len(sys.argv) < 3:
            log_error("No URL")
            showErrorNotification("No URL provided")
            xbmcplugin.setResolvedUrl(__handle__, False, xbmcgui.ListItem())
            sys.exit(1)
        
        url = sys.argv[2].lstrip('?')
        if not url:
            log_error("Empty URL")
            showErrorNotification("Empty URL")
            xbmcplugin.setResolvedUrl(__handle__, False, xbmcgui.ListItem())
            sys.exit(1)
        
        listitem = process_url_with_fallback(url)
        
        if listitem:
            xbmcplugin.setResolvedUrl(__handle__, True, listitem)
        else:
            showErrorNotification("All methods failed")
            xbmcplugin.setResolvedUrl(__handle__, False, xbmcgui.ListItem())
        
        log("=" * 80)
    
    except Exception as e:
        log_error(f"Fatal: {e}")
        import traceback
        log_error(traceback.format_exc())
        showErrorNotification(f"Error: {str(e)}")
        xbmcplugin.setResolvedUrl(__handle__, False, xbmcgui.ListItem())
