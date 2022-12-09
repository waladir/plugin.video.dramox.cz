# -*- coding: utf-8 -*-
import os
import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

from urllib.request import urlopen, Request
from urllib.parse import parse_qsl
from urllib.parse import urlencode
from urllib.error import HTTPError

import json
import codecs
import time

from xbmcvfs import translatePath

_url = sys.argv[0]
if len(sys.argv) > 1:
    _handle = int(sys.argv[1])

token = None

def get_url(**kwargs):
    return '{0}?{1}'.format(_url, urlencode(kwargs))

def call_api(url, data, method = None):
    global token
    if token is not None:
        headers = {'Authorization' : 'Bearer ' + token, 'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:107.0) Gecko/20100101 Firefox/107.0', 'Accept': 'application/json; charset=utf-8', 'Content-type' : 'application/json;charset=UTF-8'}
    else:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:107.0) Gecko/20100101 Firefox/107.0', 'Accept-language' : 'cs', 'Accept': 'application/json; charset=utf-8', 'Content-type' : 'application/json;charset=UTF-8'}
    if data != None:
        data = json.dumps(data).encode("utf-8")
    if method is not None:
        request = Request(url = url, data = data, method = method, headers = headers)
    else:
        request = Request(url = url, data = data, headers = headers)
    try:
        html = urlopen(request).read()
        if html and len(html) > 0:
            data = json.loads(html)
            return data
        else:
            return []
    except HTTPError as e:
        return { 'err' : e.reason }      

def get_token():
    global token
    addon = xbmcaddon.Addon()
    if not addon.getSetting('email') or len(addon.getSetting('email')) > 0 and not addon.getSetting('password') and len(addon.getSetting('password')) == 0:
        xbmcgui.Dialog().notification('Dramox', 'Zadejte v nastavení přihlašovací údaje', xbmcgui.NOTIFICATION_ERROR, 5000)
        sys.exit()
    data = None
    addon_userdata_dir = translatePath(addon.getAddonInfo('profile'))
    filename = os.path.join(addon_userdata_dir, 'session.txt')
    try:
        with codecs.open(filename, 'r', encoding='utf-8') as file:
            for row in file:
                data = row[:-1]
    except IOError as error:
        if error.errno != 2:
            xbmcgui.Dialog().notification('České kino', 'Chyba při načtení session', xbmcgui.NOTIFICATION_ERROR, 5000)
    if data is not None:
        data = json.loads(data)
        if 'token' in data and 'valid_to' in data and data['valid_to'] > int(time.time()):
            return data['token']
    post = {'email' : addon.getSetting('email'), 'password' : addon.getSetting('password'), 'returnSecureToken' : True}
    data = call_api(url = 'https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key=AIzaSyAixAhl9bfbPg1gOwo_Rql2ReERbr7F1tA', data = post, method = 'POST')
    if 'idToken' in data:
        token = data['idToken']
        data = json.dumps({'token' : token, 'valid_to' : int(time.time()) + 60*60})
        try:
            with codecs.open(filename, 'w', encoding='utf-8') as file:
                file.write('%s\n' % data)
        except IOError:
            xbmcgui.Dialog().notification('Dramox', 'Chyba uložení session', xbmcgui.NOTIFICATION_ERROR, 5000)
        return token
    else:
        xbmcgui.Dialog().notification('Dramox', 'Chyba při přihlášení', xbmcgui.NOTIFICATION_ERROR, 5000)
        sys.exit()

def play_stream(id):
    global token
    token = get_token()
    play = call_api(url = 'https://dramoxapi.cz/plays/' + str(id), data = None)
    if 'video' in play:
        video_id = play['video']['id']
        video = call_api(url = 'https://dramoxapi.cz/video/' + str(video_id), data = None)
        if 'streams' in video and 'dash' in video['streams']:
            url = video['streams']['dash']
            header = {'Accept' : '*/*', 'Accept-Encoding' : 'gzip, deflate, br', 'customdata' : video['custom_data']}
            from inputstreamhelper import Helper  # pylint: disable=import-outside-toplevel
            is_helper = Helper('mpd', drm = 'com.widevine.alpha')
            if is_helper.check_inputstream():
                list_item = xbmcgui.ListItem(path = url)
                list_item.setProperty('inputstream', is_helper.inputstream_addon)
                list_item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
                list_item.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
                list_item.setProperty('inputstream.adaptive.license_key', 'https://wv-keyos.licensekeyserver.com/|' + urlencode(header) + '|R{SSM}|')
                list_item.setMimeType('application/dash+xml')
                xbmcplugin.setResolvedUrl(_handle, True, list_item)

def list_theaters(label, favourites):
    xbmcplugin.setPluginCategory(_handle, label)
    addon = xbmcaddon.Addon()
    order = ''
    if addon.getSetting('order') == 'popularity':
        order = '?order_by=popularity'
    elif addon.getSetting('order') == 'abecedy':
        order = '?order_by=name'
    elif addon.getSetting('order') == 'datumu přidání':
        order = '?order_by=created'
    favourite_theaters = load_favourites()
    data = call_api(url = 'https://dramoxapi.cz/theatres' + order, data = None)
    for item in data:
        if favourites == 0 or str(item['id']) in favourite_theaters:
            if str(item['id']) in favourite_theaters and favourites == 0:
                list_item = xbmcgui.ListItem(label = '[B]' + item['name'] + '[/B]')
            else:
                list_item = xbmcgui.ListItem(label = item['name'])
            if 'poster_url' in item:
                list_item.setArt({ 'thumb' : item['poster_url'], 'icon' : item['poster_url'] })
            if str(item['id']) in favourite_theaters:
                list_item.addContextMenuItems([('Odstranit z oblíbených', 'RunPlugin(plugin://plugin.video.dramox.cz?action=remove_favourite&id=' + str(item['id']) + ')',)], replaceItems = True)                       
            else:                    
                list_item.addContextMenuItems([('Přidat do oblíbených', 'RunPlugin(plugin://plugin.video.dramox.cz?action=add_favourite&id=' + str(item['id']) + ')',)], replaceItems = True)                       
            url = get_url(action='list_theater_plays', label = item['name'], id = item['id'])  
            xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = True)    

def list_theater_plays(label, id):
    xbmcplugin.setPluginCategory(_handle, label)
    data = call_api(url = 'https://dramoxapi.cz/theatres/' + str(id), data = None)
    for item in data['plays']:
        list_item = xbmcgui.ListItem(label = item['title'])
        list_item.setInfo('video', {'mediatype' : 'movie'})
        if 'poster_url' in item:
            list_item.setArt({ 'thumb' : item['poster_url'], 'icon' : item['poster_url'] })
        url = get_url(action='play_stream', id = item['id'])  
        list_item.setProperty('IsPlayable', 'true')   
        xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = True)    

def list_genres(label):
    xbmcplugin.setPluginCategory(_handle, label)
    data = call_api(url = 'https://dramoxapi.cz/genres', data = None)
    for item in sorted(data, key=lambda d: d['id']):
        list_item = xbmcgui.ListItem(label = item['name'])
        if 'poster_url' in item:
            list_item.setArt({ 'thumb' : item['poster_url'], 'icon' : item['poster_url'] })
        url = get_url(action='list_genre_plays', label = item['name'], id = item['id'])  
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = True)    

def list_genre_plays(label, id):
    xbmcplugin.setPluginCategory(_handle, label)
    addon = xbmcaddon.Addon()
    data = call_api(url = 'https://dramoxapi.cz/genres/' + str(id), data = None)
    favourites = load_favourites()
    for item in data['plays']:
        if addon.getSetting('filter_favourites') == 'false' or str(item['theatre']['id']) in favourites:
            list_item = xbmcgui.ListItem(label = item['title'] + ' (' + item['theatre']['name'] + ')')
            list_item.setInfo('video', {'mediatype' : 'movie'})
            if 'poster_url' in item:
                list_item.setArt({ 'thumb' : item['poster_url'], 'icon' : item['poster_url'] })
            url = get_url(action='play_stream', id = item['id'])  
            list_item.setProperty('IsPlayable', 'true')   
            xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = True)    

def list_search(label):
    xbmcplugin.setPluginCategory(_handle, label)
    list_item = xbmcgui.ListItem(label='Nové hledání')
    url = get_url(action='list_search_results', query = '-----', label = label + ' / ' + 'Nové hledání')  
    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    history = load_search_history()
    for item in history:
        list_item = xbmcgui.ListItem(label=item)
        url = get_url(action='list_search_results', query = item, label = label + ' / ' + item)  
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle,cacheToDisc = False)

def list_search_results(query, label):
    if query == '-----':
        input = xbmc.Keyboard('', 'Hledat')
        input.doModal()
        if not input.isConfirmed(): 
            return
        query = input.getText()
        if len(query) == 0:
            xbmcgui.Dialog().notification('Dramox', 'Je potřeba zadat vyhledávaný řetězec', xbmcgui.NOTIFICATION_ERROR, 5000)
            return   
    save_search_history(query)
    addon = xbmcaddon.Addon()
    favourites = load_favourites()
    post = {'query' : query}
    data = call_api(url = 'https://dramoxapi.cz/search', data = post, method = 'POST')
    if 'plays' in data and len(data['plays']) > 0:
        for item in data['plays']:
            if addon.getSetting('filter_favourites') == 'false' or str(item['theatre']) in favourites:
                list_item = xbmcgui.ListItem(label = item['name'] + ' (' + item['theatre_name'] + ')')
                list_item.setInfo('video', {'mediatype' : 'movie'})
                if 'poster_url' in item:
                    list_item.setArt({ 'thumb' : item['poster_url'], 'icon' : item['poster_url'] })
                url = get_url(action='play_stream', id = item['id'])  
                list_item.setProperty('IsPlayable', 'true')   
                xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
        xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)    
    else:
        xbmcgui.Dialog().notification('Dramox','Nic nenalezeno', xbmcgui.NOTIFICATION_INFO, 3000)        

def save_search_history(query):
    addon = xbmcaddon.Addon()
    addon_userdata_dir = translatePath(addon.getAddonInfo('profile')) 
    max_history = 10
    cnt = 0
    history = []
    filename = addon_userdata_dir + 'search_history.txt'
    try:
        with codecs.open(filename, 'r') as file:
            for line in file:
                item = line[:-1]
                if item != query:
                    history.append(item)
    except IOError:
        history = []
    history.insert(0,query)
    with codecs.open(filename, 'w') as file:
        for item  in history:
            cnt = cnt + 1
            if cnt <= max_history:
                file.write('%s\n' % item)

def load_search_history():
    history = []
    addon = xbmcaddon.Addon()
    addon_userdata_dir = translatePath(addon.getAddonInfo('profile')) 
    filename = addon_userdata_dir + 'search_history.txt'
    try:
        with codecs.open(filename, 'r') as file:
            for line in file:
                item = line[:-1]
                history.append(item)
    except IOError:
        history = []
    return history

def load_favourites():
    data = []
    addon = xbmcaddon.Addon()
    addon_userdata_dir = translatePath(addon.getAddonInfo('profile'))
    filename = os.path.join(addon_userdata_dir, 'favourites.txt')
    try:
        with codecs.open(filename, 'r', encoding='utf-8') as file:
            for row in file:
                data = row[:-1]
    except IOError as error:
        if error.errno != 2:
            xbmcgui.Dialog().notification('Dramox', 'Chyba při načtení oblíbených divadel', xbmcgui.NOTIFICATION_ERROR, 5000)
            sys.exit()
        else:
            data = '[]'
    if data is not None:
        data = json.loads(data)
    return data

def save_favourites(data):
    addon = xbmcaddon.Addon()
    addon_userdata_dir = translatePath(addon.getAddonInfo('profile'))
    filename = os.path.join(addon_userdata_dir, 'favourites.txt')
    data = json.dumps(data)
    try:
        with codecs.open(filename, 'w', encoding='utf-8') as file:
            file.write('%s\n' % data)
    except IOError:
        xbmcgui.Dialog().notification('Dramox', 'Chyba uložení oblíbených divadel', xbmcgui.NOTIFICATION_ERROR, 5000)

def add_favourite(id):   
    data = load_favourites()
    data.append(str(id))
    save_favourites(data)
    xbmcgui.Dialog().notification('Dramox','Divadlo přidáno do oblíbených', xbmcgui.NOTIFICATION_INFO, 3000)        
    xbmc.executebuiltin('Container.Refresh')

def remove_favourite(id):
    data = load_favourites()
    data.remove(str(id))
    save_favourites(data)
    xbmcgui.Dialog().notification('Dramox','Divadlo odstraněno z oblíbených', xbmcgui.NOTIFICATION_INFO, 3000)        
    xbmc.executebuiltin('Container.Refresh')        

def list_menu():
    addon = xbmcaddon.Addon()
    icons_dir = os.path.join(addon.getAddonInfo('path'), 'resources','images')

    list_item = xbmcgui.ListItem(label = 'Divadla')
    url = get_url(action='list_theaters', label = 'Divadla')  
    list_item.setArt({ 'thumb' : os.path.join(icons_dir , 'theaters.png'), 'icon' : os.path.join(icons_dir , 'theaters.png') })
    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)

    list_item = xbmcgui.ListItem(label = 'Žánry')
    url = get_url(action='list_genres', label = 'Žánry')  
    list_item.setArt({ 'thumb' : os.path.join(icons_dir , 'genres.png'), 'icon' : os.path.join(icons_dir , 'genres.png') })
    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)

    list_item = xbmcgui.ListItem(label = 'Oblíbená divadla')
    url = get_url(action='list_favourites', label = 'Oblíbená divadla')  
    list_item.setArt({ 'thumb' : os.path.join(icons_dir , 'favourites.png'), 'icon' : os.path.join(icons_dir , 'favourites.png') })
    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)

    list_item = xbmcgui.ListItem(label = 'Hledat')
    url = get_url(action='list_search', label = 'Hledat')  
    list_item.setArt({ 'thumb' : os.path.join(icons_dir , 'search.png'), 'icon' : os.path.join(icons_dir , 'search.png') })
    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)

    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)    

def router(paramstring):
    params = dict(parse_qsl(paramstring))
    if params:
        if params['action'] == 'list_theaters':
            list_theaters(label = params['label'], favourites = 0)
        elif params['action'] == 'list_favourites':
            list_theaters(label = params['label'], favourites = 1)
        elif params['action'] == 'list_theater_plays':
            list_theater_plays(label = params['label'], id = params['id'])
        elif params['action'] == 'list_genres':
            list_genres(label = params['label'])
        elif params['action'] == 'list_genre_plays':
            list_genre_plays(label = params['label'], id = params['id'])
        elif params['action'] == 'play_stream':
            play_stream(id = params['id'])
        elif params['action'] == 'list_search':
            list_search(label = params['label'])
        elif params['action'] == 'list_search_results':
            list_search_results(query = params['query'], label = params['label'])
        elif params['action'] == 'add_favourite':
            add_favourite(id = params['id'])
        elif params['action'] == 'remove_favourite':
            remove_favourite(id = params['id'])
        else:
            raise ValueError('Neznámý parametr: {0}!'.format(paramstring))
    else:
         list_menu()

if __name__ == '__main__':
    router(sys.argv[2][1:])
